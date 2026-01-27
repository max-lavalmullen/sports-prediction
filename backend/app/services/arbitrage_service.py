"""
Arbitrage Detection Service.

Finds cross-book arbitrage opportunities and middle bets by comparing
odds across all available sportsbooks.

Arbitrage = guaranteed profit regardless of outcome (rare, short-lived)
Middle = win both sides if score lands in a specific range
Low-hold = combined vig < 2%, good for value betting
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger
import json

from data.apis.odds_api import OddsService, GameOdds, OddsLine, Market
from app.core.database import get_db_connection


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage or middle opportunity."""
    game_id: str
    sport: str
    home_team: str
    away_team: str
    market_type: str  # h2h, spreads, totals
    opportunity_type: str  # arbitrage, middle, low_hold

    # Side 1
    book1: str
    selection1: str
    odds1: int
    odds1_decimal: float
    line1: Optional[float] = None

    # Side 2
    book2: str
    selection2: str
    odds2: int
    odds2_decimal: float
    line2: Optional[float] = None

    # Side 3 (for 3-way markets like soccer)
    book3: Optional[str] = None
    selection3: Optional[str] = None
    odds3: Optional[int] = None
    odds3_decimal: Optional[float] = None

    # Calculations
    profit_pct: float = 0.0
    stake1_pct: float = 0.0  # % of total stake on side 1
    stake2_pct: float = 0.0  # % of total stake on side 2
    stake3_pct: float = 0.0  # % of total stake on side 3
    middle_size: Optional[float] = None  # For middles: size of the window

    # Metadata
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    combined_hold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "market_type": self.market_type,
            "opportunity_type": self.opportunity_type,
            "book1": self.book1,
            "selection1": self.selection1,
            "odds1": self.odds1,
            "line1": self.line1,
            "book2": self.book2,
            "selection2": self.selection2,
            "odds2": self.odds2,
            "line2": self.line2,
            "book3": self.book3,
            "selection3": self.selection3,
            "odds3": self.odds3,
            "profit_pct": round(self.profit_pct, 4),
            "stake1_pct": round(self.stake1_pct, 4),
            "stake2_pct": round(self.stake2_pct, 4),
            "stake3_pct": round(self.stake3_pct, 4),
            "middle_size": self.middle_size,
            "combined_hold": self.combined_hold,
            "detected_at": self.detected_at,
        }


class ArbitrageService:
    """
    Detect arbitrage opportunities across sportsbooks.

    Usage:
        service = ArbitrageService()
        arbs = service.find_arbitrage("nba")
        middles = service.find_middles("nfl")
    """

    def __init__(self, odds_service: Optional[OddsService] = None):
        """
        Initialize arbitrage service.

        Args:
            odds_service: OddsService instance (creates new one if not provided)
        """
        self.odds_service = odds_service or OddsService()

    def find_all_opportunities(
        self,
        sport: str,
        include_arbs: bool = True,
        include_middles: bool = True,
        include_low_hold: bool = True,
        max_hold_pct: float = 2.0,
        save_to_db: bool = True,
    ) -> List[ArbitrageOpportunity]:
        """
        Find all betting opportunities for a sport.

        Args:
            sport: Sport key (nba, nfl, etc.)
            include_arbs: Include true arbitrage (guaranteed profit)
            include_middles: Include middle opportunities
            include_low_hold: Include low-hold markets
            max_hold_pct: Maximum combined hold for low-hold detection
            save_to_db: Whether to save found opportunities to database

        Returns:
            List of opportunities sorted by profit potential
        """
        odds_list = self.odds_service.get_current_odds(sport)

        if not odds_list:
            logger.warning(f"No odds available for {sport}")
            return []

        opportunities = []

        for game in odds_list:
            # Check moneylines
            if include_arbs:
                # 2-way arbs
                arbs = self._find_moneyline_arb(game)
                opportunities.extend(arbs)

                # 3-way arbs (Soccer)
                if any(kw in game.sport.lower() for kw in ["soccer", "football"]):
                    soccer_arbs = self._find_3way_moneyline_arb(game)
                    opportunities.extend(soccer_arbs)

            # Check spreads for middles
            if include_middles:
                middles = self._find_spread_middles(game)
                opportunities.extend(middles)

                total_middles = self._find_total_middles(game)
                opportunities.extend(total_middles)

            # Check for low-hold markets
            if include_low_hold:
                low_holds = self._find_low_hold_markets(game, max_hold_pct)
                opportunities.extend(low_holds)

        # Sort by profit potential
        opportunities.sort(key=lambda x: x.profit_pct, reverse=True)

        if save_to_db and opportunities:
            self._save_opportunities(opportunities)

        logger.info(f"Found {len(opportunities)} opportunities for {sport}")

        return opportunities

    def _save_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """Save found opportunities to database."""
        conn = get_db_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                # First, mark all active arbs for these games as inactive
                game_ids = list(set([o.game_id for o in opportunities]))
                cur.execute(
                    "UPDATE arbitrage_opportunities SET is_active = FALSE WHERE game_id = ANY(%s)",
                    (game_ids,)
                )

                for opp in opportunities:
                    cur.execute(
                        """
                        INSERT INTO arbitrage_opportunities (
                            game_id, sport, market_type, opportunity_type,
                            book1, selection1, odds1_american, odds1_decimal, line1,
                            book2, selection2, odds2_american, odds2_decimal, line2,
                            book3, selection3, odds3_american, odds3_decimal,
                            profit_pct, stake1_pct, stake2_pct, stake3_pct,
                            middle_size, combined_hold, is_active
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, TRUE
                        )
                        ON CONFLICT (game_id, market_type, book1, book2, book3, selection1, selection2, selection3, line1, line2)
                        DO UPDATE SET
                            last_seen_at = NOW(),
                            is_active = TRUE,
                            profit_pct = EXCLUDED.profit_pct,
                            odds1_american = EXCLUDED.odds1_american,
                            odds1_decimal = EXCLUDED.odds1_decimal,
                            odds2_american = EXCLUDED.odds2_american,
                            odds2_decimal = EXCLUDED.odds2_decimal,
                            odds3_american = EXCLUDED.odds3_american,
                            odds3_decimal = EXCLUDED.odds3_decimal
                        """,
                        (
                            opp.game_id, opp.sport, opp.market_type, opp.opportunity_type,
                            opp.book1, opp.selection1, opp.odds1, opp.odds1_decimal, opp.line1,
                            opp.book2, opp.selection2, opp.odds2, opp.odds2_decimal, opp.line2,
                            opp.book3, opp.selection3, opp.odds3, opp.odds3_decimal,
                            opp.profit_pct, opp.stake1_pct, opp.stake2_pct, opp.stake3_pct,
                            opp.middle_size, opp.combined_hold
                        )
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving arbitrage opportunities: {e}")
            conn.rollback()
        finally:
            conn.close()

    def find_arbitrage(self, sport: str) -> List[ArbitrageOpportunity]:
        """Find pure arbitrage opportunities (guaranteed profit)."""
        return self.find_all_opportunities(
            sport,
            include_arbs=True,
            include_middles=False,
            include_low_hold=False
        )

    def find_middles(self, sport: str) -> List[ArbitrageOpportunity]:
        """Find middle opportunities (potential to win both sides)."""
        return self.find_all_opportunities(
            sport,
            include_arbs=False,
            include_middles=True,
            include_low_hold=False
        )

    def _find_3way_moneyline_arb(self, game: GameOdds) -> List[ArbitrageOpportunity]:
        """
        Find 3-way moneyline arbitrage (Soccer).
        
        Arbitrage exists when: (1/odds1) + (1/odds2) + (1/odds3) < 1
        """
        arbs = []
        
        home_lines = [l for l in game.moneyline if l.selection == game.home_team]
        away_lines = [l for l in game.moneyline if l.selection == game.away_team]
        draw_lines = [l for l in game.moneyline if l.selection.lower() == "draw"]
        
        if not home_lines or not away_lines or not draw_lines:
            return []
            
        for h in home_lines:
            for a in away_lines:
                for d in draw_lines:
                    # At least two different books must be involved
                    if h.bookmaker == a.bookmaker == d.bookmaker:
                        continue
                        
                    implied_h = 1 / h.price_decimal
                    implied_a = 1 / a.price_decimal
                    implied_d = 1 / d.price_decimal
                    total_implied = implied_h + implied_a + implied_d
                    
                    if total_implied < 1.0:
                        profit_pct = (1 - total_implied) * 100
                        
                        stake_h = implied_h / total_implied
                        stake_a = implied_a / total_implied
                        stake_d = implied_d / total_implied
                        
                        arbs.append(ArbitrageOpportunity(
                            game_id=game.game_id,
                            sport=game.sport,
                            home_team=game.home_team,
                            away_team=game.away_team,
                            market_type="h2h",
                            opportunity_type="arbitrage",
                            book1=h.bookmaker,
                            selection1=game.home_team,
                            odds1=h.price,
                            odds1_decimal=h.price_decimal,
                            book2=a.bookmaker,
                            selection2=game.away_team,
                            odds2=a.price,
                            odds2_decimal=a.price_decimal,
                            book3=d.bookmaker,
                            selection3="Draw",
                            odds3=d.price,
                            odds3_decimal=d.price_decimal,
                            profit_pct=profit_pct,
                            stake1_pct=stake_h * 100,
                            stake2_pct=stake_a * 100,
                            stake3_pct=stake_d * 100,
                            combined_hold=(total_implied - 1) * 100,
                        ))
        return arbs

    def _find_moneyline_arb(self, game: GameOdds) -> List[ArbitrageOpportunity]:
        """
        Find 2-way moneyline arbitrage.
        """
        arbs = []

        home_lines = [l for l in game.moneyline if l.selection == game.home_team]
        away_lines = [l for l in game.moneyline if l.selection == game.away_team]

        for home_line in home_lines:
            for away_line in away_lines:
                if home_line.bookmaker == away_line.bookmaker:
                    continue

                implied_home = 1 / home_line.price_decimal
                implied_away = 1 / away_line.price_decimal
                total_implied = implied_home + implied_away

                if total_implied < 1.0:
                    profit_pct = (1 - total_implied) * 100
                    stake1_pct = implied_away / total_implied
                    stake2_pct = implied_home / total_implied

                    arbs.append(ArbitrageOpportunity(
                        game_id=game.game_id,
                        sport=game.sport,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        market_type="h2h",
                        opportunity_type="arbitrage",
                        book1=home_line.bookmaker,
                        selection1=game.home_team,
                        odds1=home_line.price,
                        odds1_decimal=home_line.price_decimal,
                        book2=away_line.bookmaker,
                        selection2=game.away_team,
                        odds2=away_line.price,
                        odds2_decimal=away_line.price_decimal,
                        profit_pct=profit_pct,
                        stake1_pct=stake1_pct * 100,
                        stake2_pct=stake2_pct * 100,
                        combined_hold=(total_implied - 1) * 100,
                    ))

        return arbs

    def _find_spread_middles(self, game: GameOdds) -> List[ArbitrageOpportunity]:
        """
        Find spread middle opportunities.

        Middle exists when spread at Book A < spread at Book B
        Example: Book A has Home -3, Book B has Away +4.5
                 If Home wins by exactly 4, both bets win!
        """
        middles = []

        # Get all spread lines
        home_spreads = [(l.bookmaker, l.point, l.price, l.price_decimal)
                        for l in game.spread
                        if l.selection == game.home_team and l.point is not None]

        away_spreads = [(l.bookmaker, l.point, l.price, l.price_decimal)
                        for l in game.spread
                        if l.selection == game.away_team and l.point is not None]

        # Check for overlapping spreads
        for home_book, home_line, home_odds, home_dec in home_spreads:
            for away_book, away_line, away_odds, away_dec in away_spreads:
                # Skip same bookmaker
                if home_book == away_book:
                    continue

                # Middle exists if home spread + away spread > 0
                # e.g., Home -3 and Away +4.5 = middle of 1.5 points
                middle_size = home_line + away_line  # Note: home is negative

                # Actually, for a middle: away_line > abs(home_line)
                # If home is -3 and away is +4, middle size is 1
                if away_line > abs(home_line):
                    actual_middle = away_line - abs(home_line)

                    # Calculate expected value of middle
                    # This is approximate - true EV depends on score distribution
                    implied_home = 1 / home_dec
                    implied_away = 1 / away_dec

                    # If both sides are -110, we need middle to hit ~5% to break even
                    # Profit if middle hits = payout - losing side
                    # Very rough approximation for now

                    middles.append(ArbitrageOpportunity(
                        game_id=game.game_id,
                        sport=game.sport,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        market_type="spreads",
                        opportunity_type="middle",
                        book1=home_book,
                        selection1=f"{game.home_team} {home_line}",
                        odds1=home_odds,
                        odds1_decimal=home_dec,
                        line1=home_line,
                        book2=away_book,
                        selection2=f"{game.away_team} +{away_line}",
                        odds2=away_odds,
                        odds2_decimal=away_dec,
                        line2=away_line,
                        profit_pct=0,  # Depends on middle hitting
                        stake1_pct=50,  # Even stakes for middles
                        stake2_pct=50,
                        middle_size=actual_middle,
                        combined_hold=(implied_home + implied_away - 1) * 100,
                    ))

        return middles

    def _find_total_middles(self, game: GameOdds) -> List[ArbitrageOpportunity]:
        """
        Find total (over/under) middle opportunities.

        Example: Book A has Over 220, Book B has Under 222.5
                 If total is 221 or 222, both bets win!
        """
        middles = []

        # Get all total lines
        overs = [(l.bookmaker, l.point, l.price, l.price_decimal)
                 for l in game.total
                 if l.selection.lower() == "over" and l.point is not None]

        unders = [(l.bookmaker, l.point, l.price, l.price_decimal)
                  for l in game.total
                  if l.selection.lower() == "under" and l.point is not None]

        # Check for overlapping totals
        for over_book, over_line, over_odds, over_dec in overs:
            for under_book, under_line, under_odds, under_dec in unders:
                # Skip same bookmaker
                if over_book == under_book:
                    continue

                # Middle exists if over_line < under_line
                if over_line < under_line:
                    middle_size = under_line - over_line

                    implied_over = 1 / over_dec
                    implied_under = 1 / under_dec

                    middles.append(ArbitrageOpportunity(
                        game_id=game.game_id,
                        sport=game.sport,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        market_type="totals",
                        opportunity_type="middle",
                        book1=over_book,
                        selection1=f"Over {over_line}",
                        odds1=over_odds,
                        odds1_decimal=over_dec,
                        line1=over_line,
                        book2=under_book,
                        selection2=f"Under {under_line}",
                        odds2=under_odds,
                        odds2_decimal=under_dec,
                        line2=under_line,
                        profit_pct=0,
                        stake1_pct=50,
                        stake2_pct=50,
                        middle_size=middle_size,
                        combined_hold=(implied_over + implied_under - 1) * 100,
                    ))

        return middles

    def _find_low_hold_markets(
        self,
        game: GameOdds,
        max_hold_pct: float = 2.0
    ) -> List[ArbitrageOpportunity]:
        """
        Find markets with low combined hold (vig).

        Low-hold markets are good for value betting even without arbitrage.
        Combined hold = (implied_1 + implied_2 - 1) * 100
        """
        low_holds = []

        # Check all book pairs for moneylines
        home_lines = [l for l in game.moneyline if l.selection == game.home_team]
        away_lines = [l for l in game.moneyline if l.selection == game.away_team]

        for home_line in home_lines:
            for away_line in away_lines:
                if home_line.bookmaker != away_line.bookmaker:
                    continue  # Same book for low-hold

                implied_home = 1 / home_line.price_decimal
                implied_away = 1 / away_line.price_decimal
                hold = (implied_home + implied_away - 1) * 100

                if hold <= max_hold_pct and hold > 0:  # Don't include arbs
                    low_holds.append(ArbitrageOpportunity(
                        game_id=game.game_id,
                        sport=game.sport,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        market_type="h2h",
                        opportunity_type="low_hold",
                        book1=home_line.bookmaker,
                        selection1=game.home_team,
                        odds1=home_line.price,
                        odds1_decimal=home_line.price_decimal,
                        book2=away_line.bookmaker,
                        selection2=game.away_team,
                        odds2=away_line.price,
                        odds2_decimal=away_line.price_decimal,
                        profit_pct=-hold,  # Negative since it's a cost, not profit
                        stake1_pct=50,
                        stake2_pct=50,
                        combined_hold=hold,
                    ))

        return low_holds

    def calculate_stakes(
        self,
        total_stake: float,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Calculate optimal stake amounts for an arbitrage opportunity.

        Args:
            total_stake: Total amount to wager
            opportunity: ArbitrageOpportunity object

        Returns:
            Dict with stakes and guaranteed_profit
        """
        stake1 = total_stake * (opportunity.stake1_pct / 100)
        stake2 = total_stake * (opportunity.stake2_pct / 100)
        stake3 = total_stake * (opportunity.stake3_pct / 100)

        # Calculate guaranteed profit
        payout1 = stake1 * opportunity.odds1_decimal
        payout2 = stake2 * opportunity.odds2_decimal
        payout3 = (stake3 * opportunity.odds3_decimal) if opportunity.odds3_decimal else payout1

        # All payouts should be roughly equal for true arb
        guaranteed_payout = min(payout1, payout2, payout3)
        guaranteed_profit = guaranteed_payout - total_stake

        result = {
            "stake1": round(stake1, 2),
            "stake2": round(stake2, 2),
            "book1": opportunity.book1,
            "book2": opportunity.book2,
            "selection1": opportunity.selection1,
            "selection2": opportunity.selection2,
            "guaranteed_profit": round(guaranteed_profit, 2),
            "profit_pct": round((guaranteed_profit / total_stake) * 100, 2),
        }

        if opportunity.book3:
            result["stake3"] = round(stake3, 2)
            result["book3"] = opportunity.book3
            result["selection3"] = opportunity.selection3

        return result


# Singleton instance
arbitrage_service = ArbitrageService()


def find_arbitrage(sport: str) -> List[Dict[str, Any]]:
    """Convenience function to find arbitrage opportunities."""
    opps = arbitrage_service.find_arbitrage(sport)
    return [o.to_dict() for o in opps]


def find_all_opportunities(sport: str) -> List[Dict[str, Any]]:
    """Convenience function to find all betting opportunities."""
    opps = arbitrage_service.find_all_opportunities(sport)
    return [o.to_dict() for o in opps]
