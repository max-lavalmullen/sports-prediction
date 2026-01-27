"""
Strategy Executor.
Orchestrates bot actions based on strategy configurations.
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.bot.base_bot import BaseBettingBot
from app.services.bot.paper_bot import PaperTradingBot

class StrategyExecutor:
    """
    Executes betting strategies by connecting predictions to bots.
    """

    def __init__(self, bot: Optional[BaseBettingBot] = None):
        self.bot = bot or PaperTradingBot()
        self.strategies = [] # Load from DB in real implementation

    def process_prediction(self, prediction: Dict[str, Any]):
        """
        Evaluate a new prediction against all active strategies.
        """
        # Example strategy logic
        sport = prediction.get('sport')
        edge = prediction.get('edge', 0)
        
        # Simple hardcoded strategy for now
        if edge >= 0.05:
            logger.info(f"Strategy triggered for {sport} game {prediction.get('game_id')} with edge {edge}")
            
            # Calculate stake (simplified)
            balance = self.bot.get_balance()
            stake = balance * 0.02 # 2% flat stake
            
            # Place bet
            self.bot.place_bet(
                game_id=prediction.get('game_id'),
                selection=prediction.get('selection'),
                odds=prediction.get('odds'),
                stake=stake
            )

# Singleton
strategy_executor = StrategyExecutor()
