"""
Celery tasks for arbitrage detection and alerts.
"""

from datetime import datetime
from typing import List, Optional
from celery import shared_task
from loguru import logger
import asyncio

from app.services.arbitrage_service import arbitrage_service
from app.api.websocket.alerts import push_arbitrage_alert

@shared_task
def detect_arbitrage_task(sports: Optional[List[str]] = None):
    """
    Detect arbitrage opportunities across all sports.
    Runs every minute.
    """
    if sports is None:
        sports = ['nba', 'nfl', 'mlb', 'soccer']
    
    all_opportunities = []
    
    for sport in sports:
        try:
            # This will find arbs, middles, and save to DB
            opportunities = arbitrage_service.find_all_opportunities(
                sport=sport,
                include_arbs=True,
                include_middles=True,
                include_low_hold=False,
                save_to_db=True
            )
            
            # Filter for true arbitrage to send alerts
            arbs = [o for o in opportunities if o.opportunity_type == "arbitrage"]
            
            for arb in arbs:
                # Prepare alert data
                alert = {
                    "type": "arbitrage_alert",
                    "sport": arb.sport,
                    "game_id": arb.game_id,
                    "home_team": arb.home_team,
                    "away_team": arb.away_team,
                    "market_type": arb.market_type,
                    "profit_pct": arb.profit_pct,
                    "book1": arb.book1,
                    "selection1": arb.selection1,
                    "odds1": arb.odds1,
                    "book2": arb.book2,
                    "selection2": arb.selection2,
                    "odds2": arb.odds2,
                }
                
                if arb.book3:
                    alert["book3"] = arb.book3
                    alert["selection3"] = arb.selection3
                    alert["odds3"] = arb.odds3

                # Push alert via WebSocket (need to wrap in async)
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.run_until_complete(push_arbitrage_alert(alert))
                
            all_opportunities.extend(opportunities)
            
        except Exception as e:
            logger.error(f"Error detecting arbitrage for {sport}: {e}")
            
    return {
        "timestamp": datetime.now().isoformat(),
        "total_opportunities": len(all_opportunities),
        "arbs_found": sum(1 for o in all_opportunities if o.opportunity_type == "arbitrage"),
    }
