from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from app.core.database import Base
from datetime import datetime

class BotExecution(Base):
    __tablename__ = "bot_executions"

    id = Column(String(50), primary_key=True)
    strategy_id = Column(Integer, nullable=False)
    bot_type = Column(String(50), nullable=False)
    bot_id = Column(String(50), default="default")
    game_id = Column(Integer, ForeignKey("games.id"))
    prediction_id = Column(Integer, ForeignKey("predictions.id"))
    selection = Column(String(100))
    action = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    stake = Column(Float)
    odds = Column(Float)
    pnl = Column(Float)
    current_balance = Column(Float)
    reason = Column(Text)
    executed_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime)
