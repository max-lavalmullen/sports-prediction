"""
Backtesting Service.
Runs historical simulations of betting strategies.
"""

import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from sqlalchemy import select, and_, func

from app.core.database import get_db_connection
from app.models.bet import BetType
from app.models.game import GameStatus

class BacktestService:
    """
    Service for running historical backtests.
    """

    async def run_backtest(
        self,
        sports: List[str],
        start_date: date,
        end_date: date,
        initial_bankroll: float,
        strategy_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a backtest on historical data.
        """
        logger.info(f"Running backtest from {start_date} to {end_date}")
        
        conn = get_db_connection()
        if not conn:
            raise Exception("Could not connect to database")

        try:
            with conn.cursor() as cur:
                # 1. Fetch historical games with results and predictions
                cur.execute(
                    """
                    SELECT 
                        g.id, g.sport, g.home_score, g.away_score, g.scheduled_time,
                        p.id as prediction_id, p.prediction_type, p.prediction,
                        t_home.name as home_team, t_away.name as away_team
                    FROM games g
                    JOIN predictions p ON g.id = p.game_id
                    JOIN teams t_home ON g.home_team_id = t_home.id
                    JOIN teams t_away ON g.away_team_id = t_away.id
                    WHERE g.sport = ANY(%s)
                    AND g.scheduled_time BETWEEN %s AND %s
                    AND g.status = 'final'
                    ORDER BY g.scheduled_time ASC
                    """,
                    (sports, start_date, end_date)
                )
                
                rows = cur.fetchall()
                logger.info(f"Found {len(rows)} game-prediction pairs for backtest")

                # 2. Simulate day by day
                bankroll = initial_bankroll
                bets = []
                equity_curve = [{"date": start_date.isoformat(), "bankroll": bankroll, "cumulative_pl": 0}]
                
                # Group rows by date for easier simulation
                games_by_date = {}
                for row in rows:
                    g_date = row[4].date().isoformat()
                    if g_date not in games_by_date:
                        games_by_date[g_date] = []
                    games_by_date[g_date].append(row)

                sorted_dates = sorted(games_by_date.keys())
                
                for g_date in sorted_dates:
                    daily_games = games_by_date[g_date]
                    
                    for game in daily_games:
                        (g_id, sport, home_score, away_score, scheduled_time, 
                         pred_id, pred_type, pred_json, home_team, away_team) = game
                        
                        # 3. Get historical odds for this game (at time of game start or earlier)
                        # We'll use the best available odds in the history for that market
                        cur.execute(
                            """
                            SELECT sportsbook, selection, odds_decimal, line
                            FROM odds_history
                            WHERE game_id = %s
                            AND time <= %s
                            ORDER BY time DESC
                            LIMIT 50
                            """,
                            (g_id, scheduled_time)
                        )
                        odds_rows = cur.fetchall()
                        if not odds_rows:
                            continue

                        # Apply strategy to find bets
                        found_bets = self._apply_strategy(
                            game=game,
                            odds=odds_rows,
                            config=strategy_config,
                            current_bankroll=bankroll
                        )
                        
                        for bet in found_bets:
                            # 4. Settle bet
                            win_loss, pnl = self._settle_bet(bet, home_score, away_score)
                            
                            bet['result'] = win_loss
                            bet['pnl'] = pnl
                            bankroll += pnl
                            
                            bets.append(bet)
                    
                    equity_curve.append({
                        "date": g_date,
                        "bankroll": bankroll,
                        "cumulative_pl": bankroll - initial_bankroll
                    })

                # 5. Calculate Metrics
                metrics = self._calculate_metrics(bets, initial_bankroll, bankroll, equity_curve)
                
                return {
                    **metrics,
                    "equity_curve": equity_curve,
                    "total_bets_count": len(bets)
                }

        except Exception as e:
            logger.error(f"Error in backtest: {e}")
            raise
        finally:
            conn.close()

    def _apply_strategy(self, game, odds, config, current_bankroll) -> List[Dict[str, Any]]:
        """Apply strategy logic to find betting opportunities."""
        (g_id, sport, home_score, away_score, scheduled_time, 
         pred_id, pred_type, pred_json, home_team, away_team) = game
        
        min_edge = config.get('min_edge', 0.03)
        kelly_fraction = config.get('kelly_fraction', 0.25)
        max_stake_pct = config.get('max_stake_pct', 0.05)
        
        bets = []
        
        # 1. Moneyline
        if pred_type == 'moneyline':
            home_prob = pred_json.get('home_prob')
            away_prob = pred_json.get('away_prob')
            
            if home_prob and away_prob:
                best_home = 0
                best_away = 0
                for book, selection, odds_dec, line in odds:
                    if selection.lower() == home_team.lower():
                        best_home = max(best_home, float(odds_dec))
                    elif selection.lower() == away_team.lower():
                        best_away = max(best_away, float(odds_dec))

                if best_home > 1:
                    edge = home_prob - (1 / best_home)
                    if edge >= min_edge:
                        stake = self._calculate_stake(home_prob, best_home, kelly_fraction, max_stake_pct, current_bankroll)
                        bets.append({"game_id": g_id, "prediction_id": pred_id, "bet_type": "moneyline", "selection": "home", "odds": best_home, "stake": stake, "edge": edge})
                
                if best_away > 1:
                    edge = away_prob - (1 / best_away)
                    if edge >= min_edge:
                        stake = self._calculate_stake(away_prob, best_away, kelly_fraction, max_stake_pct, current_bankroll)
                        bets.append({"game_id": g_id, "prediction_id": pred_id, "bet_type": "moneyline", "selection": "away", "odds": best_away, "stake": stake, "edge": edge})

        # 2. Spread
        elif pred_type == 'spread':
            # pred_json: {home_spread: -3.5, home_prob: 0.55, ...}
            h_spread = pred_json.get('home_spread')
            h_prob = pred_json.get('home_prob')
            
            if h_spread is not None and h_prob is not None:
                # Find matching odds for this specific line
                best_odds = 0
                for book, selection, odds_dec, line in odds:
                    if line == h_spread and selection.lower() == home_team.lower():
                        best_odds = max(best_odds, float(odds_dec))
                
                if best_odds > 1:
                    edge = h_prob - (1 / best_odds)
                    if edge >= min_edge:
                        stake = self._calculate_stake(h_prob, best_odds, kelly_fraction, max_stake_pct, current_bankroll)
                        bets.append({"game_id": g_id, "prediction_id": pred_id, "bet_type": "spread", "selection": "home", "line": h_spread, "odds": best_odds, "stake": stake, "edge": edge})

        # 3. Total
        elif pred_type == 'total':
            # pred_json: {total: 220.5, over_prob: 0.53, ...}
            line_val = pred_json.get('total')
            over_prob = pred_json.get('over_prob')
            
            if line_val is not None and over_prob is not None:
                best_over = 0
                best_under = 0
                for book, selection, odds_dec, line in odds:
                    if line == line_val:
                        if selection.lower() == "over":
                            best_over = max(best_over, float(odds_dec))
                        elif selection.lower() == "under":
                            best_under = max(best_under, float(odds_dec))

                if best_over > 1:
                    edge = over_prob - (1 / best_over)
                    if edge >= min_edge:
                        stake = self._calculate_stake(over_prob, best_over, kelly_fraction, max_stake_pct, current_bankroll)
                        bets.append({"game_id": g_id, "prediction_id": pred_id, "bet_type": "total", "selection": "over", "line": line_val, "odds": best_over, "stake": stake, "edge": edge})

        return bets

    def _calculate_stake(
        self,
        win_prob: float,
        decimal_odds: float,
        kelly_fraction: float,
        max_stake_pct: float,
        bankroll: float
    ) -> float:
        """
        Calculate stake using Kelly Criterion.

        Kelly formula: f* = (bp - q) / b
        Where:
            b = decimal odds - 1 (net odds)
            p = probability of winning
            q = probability of losing (1 - p)
        """
        b = decimal_odds - 1
        p = win_prob
        q = 1 - p

        # Full Kelly
        if b <= 0:
            return 0

        full_kelly = (b * p - q) / b

        # Apply fractional Kelly and cap
        if full_kelly <= 0:
            return 0

        stake_pct = min(full_kelly * kelly_fraction, max_stake_pct)
        stake = bankroll * stake_pct

        return max(0, stake)

    def _settle_bet(self, bet, home_score, away_score) -> Tuple[str, float]:
        """Settle a bet and return (result, pnl)."""
        b_type = bet['bet_type']
        selection = bet['selection']
        odds = bet['odds']
        stake = bet['stake']
        line = bet.get('line', 0)
        
        result = "loss"
        
        if b_type == "moneyline":
            if selection == "home" and home_score > away_score: result = "win"
            elif selection == "away" and away_score > home_score: result = "win"
            elif home_score == away_score: result = "push"
            
        elif b_type == "spread":
            if selection == "home":
                score_diff = home_score + line - away_score
                if score_diff > 0: result = "win"
                elif score_diff == 0: result = "push"
            else: # away
                score_diff = away_score - line - home_score # Note: if we bet away +3.5, it's AwayScore + 3.5 > HomeScore
                # But our 'line' is usually the home line. This needs care.
                # Assuming 'line' in bet is the point spread for the SELECTION.
                score_diff = away_score + line - home_score
                if score_diff > 0: result = "win"
                elif score_diff == 0: result = "push"
                
        elif b_type == "total":
            total = home_score + away_score
            if selection == "over":
                if total > line: result = "win"
                elif total == line: result = "push"
            else: # under
                if total < line: result = "win"
                elif total == line: result = "push"
        
        if result == "win":
            pnl = stake * (odds - 1)
        elif result == "push":
            pnl = 0
            result = "push"
        else:
            pnl = -stake
            
        return result, pnl

    def _calculate_metrics(self, bets, initial, final, equity) -> Dict[str, Any]:
        """Calculate performance metrics."""
        if not bets:
            return {"roi": 0, "total_bets": 0, "wins": 0, "pushes": 0, "win_rate": 0}

        wins = sum(1 for b in bets if b['result'] == 'win')
        pushes = sum(1 for b in bets if b['result'] == 'push')
        losses = len(bets) - wins - pushes
        total_staked = sum(b['stake'] for b in bets)
        total_profit = final - initial

        # Calculate max drawdown
        peak = initial
        max_dd = 0
        for point in equity:
            bankroll = point.get('bankroll', initial)
            if bankroll > peak:
                peak = bankroll
            dd = (peak - bankroll) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return {
            "total_bets": len(bets),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": wins / len(bets) if bets else 0,
            "total_profit": total_profit,
            "roi": total_profit / total_staked if total_staked > 0 else 0,
            "initial_bankroll": initial,
            "final_bankroll": final,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd * 100
        }

# Singleton
backtest_service = BacktestService()
