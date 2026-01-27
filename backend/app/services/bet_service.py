"""
Bet service - Celery tasks for bet management.
"""
import asyncio
from datetime import datetime
from celery import shared_task
from loguru import logger
from sqlalchemy import select
from typing import Tuple, Optional

from app.core.database import AsyncSessionLocal
from app.models.bet import Bet, BetResult, BetType
from app.models.game import Game, GameStatus


def grade_bet(bet: Bet, game: Game) -> Tuple[BetResult, float]:
    """
    Determine the result of a bet based on the game outcome.
    Returns (BetResult, ProfitLoss).
    """
    if game.home_score is None or game.away_score is None:
        return BetResult.PENDING, 0.0

    # Parse common fields
    home_score = game.home_score
    away_score = game.away_score
    total_score = home_score + away_score
    
    # Normalize selection for comparison (assuming selection contains team name)
    # This is a basic implementation and might need refinement based on exact string formats
    selection = bet.selection.lower()
    home_team = game.home_team.name.lower() if game.home_team else ""
    away_team = game.away_team.name.lower() if game.away_team else ""
    
    result = BetResult.PENDING
    pnl = 0.0

    try:
        if bet.bet_type == BetType.MONEYLINE:
            # Determine winner
            if home_score > away_score:
                winner = "home"
            elif away_score > home_score:
                winner = "away"
            else:
                winner = "push"
                
            # Check selection
            if winner == "push":
                result = BetResult.PUSH
            elif winner == "home" and (home_team in selection or "home" in selection):
                result = BetResult.WIN
            elif winner == "away" and (away_team in selection or "away" in selection):
                result = BetResult.WIN
            else:
                result = BetResult.LOSS

        elif bet.bet_type == BetType.SPREAD:
            # Spread logic: (Team Score + Line) > Opponent Score
            line = float(bet.line)
            
            if home_team in selection or "home" in selection:
                # Bet on Home
                adjusted_home_score = home_score + line
                if adjusted_home_score > away_score:
                    result = BetResult.WIN
                elif adjusted_home_score < away_score:
                    result = BetResult.LOSS
                else:
                    result = BetResult.PUSH
            elif away_team in selection or "away" in selection:
                # Bet on Away
                adjusted_away_score = away_score + line
                if adjusted_away_score > home_score:
                    result = BetResult.WIN
                elif adjusted_away_score < home_score:
                    result = BetResult.LOSS
                else:
                    result = BetResult.PUSH

        elif bet.bet_type == BetType.TOTAL:
            line = float(bet.line)
            is_over = "over" in selection or "o" in selection.split()[0].lower()
            is_under = "under" in selection or "u" in selection.split()[0].lower()
            
            if is_over:
                if total_score > line:
                    result = BetResult.WIN
                elif total_score < line:
                    result = BetResult.LOSS
                else:
                    result = BetResult.PUSH
            elif is_under:
                if total_score < line:
                    result = BetResult.WIN
                elif total_score > line:
                    result = BetResult.LOSS
                else:
                    result = BetResult.PUSH

    except Exception as e:
        logger.error(f"Error grading bet {bet.id}: {e}")
        return BetResult.PENDING, 0.0

    # Calculate P&L
    if result == BetResult.WIN:
        pnl = float(bet.potential_payout - bet.stake)
    elif result == BetResult.LOSS:
        pnl = -float(bet.stake)
    elif result == BetResult.PUSH:
        pnl = 0.0
        
    return result, pnl


@shared_task(name="app.services.bet_service.capture_closing_lines")
def capture_closing_lines():
    """
    Capture consensus odds at game start to calculate CLV.
    Runs every 10 minutes to check for games starting soon.
    """
    logger.info("Starting CLV capture task")
    
    from app.services.odds_service import odds_service
    from sqlalchemy import and_
    
    async def _capture():
        async with AsyncSessionLocal() as session:
            # Get pending bets for games starting within 15 mins or already started (but not captured)
            # where closing_line is still null
            now = datetime.utcnow()
            margin = timedelta(minutes=15)
            
            query = (
                select(Bet)
                .join(Game, Bet.game_id == Game.id)
                .where(
                    Bet.closing_line.is_(None),
                    Game.scheduled_time <= now + margin
                )
            )
            result = await session.execute(query)
            active_bets = result.scalars().all()
            
            captured_count = 0
            for bet in active_bets:
                game = await session.get(Game, bet.game_id)
                
                # Fetch current odds (which are the closing odds if game just started)
                odds = odds_service.get_current_odds(game.sport)
                game_odds = next((o for o in odds if o.game_id == game.external_id), None)
                
                if not game_odds:
                    continue
                
                # Get consensus line/odds
                closing_line = None
                closing_odds_decimal = None
                
                if bet.bet_type == BetType.MONEYLINE:
                    selection = bet.selection.lower()
                    best_line = game_odds.get_best_odds("h2h", selection)
                    if best_line:
                        closing_odds_decimal = best_line.price_decimal
                        closing_line = 0.0 # ML has no "line"
                
                elif bet.bet_type == BetType.SPREAD:
                    closing_line = game_odds.get_consensus_line("spreads")
                    # Also need the price at that line, but consensus_line is simplified
                    # For now, let's use the best available price for the original line if possible
                    # or just the consensus line change
                    pass
                
                elif bet.bet_type == BetType.TOTAL:
                    closing_line = game_odds.get_consensus_line("totals")
                
                if closing_line is not None or closing_odds_decimal is not None:
                    bet.closing_line = closing_line
                    
                    # Calculate CLV
                    if closing_odds_decimal:
                        # CLV = (Closing Implied Prob / Your Implied Prob) - 1
                        your_implied = 1 / float(bet.odds_decimal)
                        closing_implied = 1 / float(closing_odds_decimal)
                        bet.clv = closing_implied - your_implied
                    elif closing_line is not None and bet.line is not None:
                        # For spreads/totals, CLV can be approximated by line movement
                        # If you bet Over 220 and it closes 222, you beat the line by 2 points.
                        # We'll store the line difference for now.
                        line_diff = float(closing_line) - float(bet.line)
                        if "under" in bet.selection.lower() or bet.line < 0: # Spread is negative
                             bet.clv = -line_diff
                        else:
                             bet.clv = line_diff
                             
                    captured_count += 1
            
            await session.commit()
            return captured_count

    try:
        from datetime import timedelta
        count = asyncio.run(_capture())
        return {"status": "success", "clv_captured": count}
    except Exception as e:
        logger.error(f"Error capturing CLV: {e}")
        return {"status": "error", "error": str(e)}


@shared_task(name="app.services.bet_service.settle_pending_bets")
def settle_pending_bets():
    """Settle bets for completed games."""
    logger.info("Starting bet settlement task")

    async def _settle():
        async with AsyncSessionLocal() as session:
            # Get pending bets for completed games
            # We explicitly join Game to ensure we have score data
            query = (
                select(Bet)
                .join(Game, Bet.game_id == Game.id)
                .where(
                    Bet.result == BetResult.PENDING,
                    Game.status == GameStatus.FINAL,
                    Game.home_score.isnot(None),
                    Game.away_score.isnot(None)
                )
            )
            result = await session.execute(query)
            pending_bets = result.scalars().all()

            settled = 0
            for bet in pending_bets:
                # Eager load game if not present (though join above helps, ORM mapping might need refresh)
                game = await session.get(Game, bet.game_id)
                # Ensure team names are loaded for string matching
                # In a real app, we'd use joinedload options in the query
                await session.refresh(game, attribute_names=['home_team', 'away_team'])
                
                new_result, pnl = grade_bet(bet, game)
                
                if new_result != BetResult.PENDING:
                    bet.result = new_result
                    bet.profit_loss = pnl
                    bet.settled_at = datetime.utcnow()
                    bet.actual_result = f"{game.away_team.abbreviation} {game.away_score} - {game.home_team.abbreviation} {game.home_score}"
                    settled += 1
                    logger.info(f"Settled bet {bet.id}: {new_result} (${pnl})")

            await session.commit()
            return settled

    try:
        count = asyncio.run(_settle())
        logger.info(f"Settled {count} bets")
        return {"status": "success", "bets_settled": count}
    except Exception as e:
        logger.error(f"Error settling bets: {e}")
        return {"status": "error", "error": str(e)}
