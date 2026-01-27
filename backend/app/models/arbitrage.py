from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index, UniqueConstraint
from app.core.database import Base
from datetime import datetime

class ArbitrageOpportunity(Base):
    __tablename__ = "arbitrage_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String(50), nullable=False)
    sport = Column(String(50), nullable=False)
    market_type = Column(String(50), nullable=False)
    opportunity_type = Column(String(50), nullable=False)
    
    book1 = Column(String(50), nullable=False)
    selection1 = Column(String(100), nullable=False)
    odds1_american = Column(Integer)
    odds1_decimal = Column(Float, nullable=False)
    line1 = Column(Float)
    
    book2 = Column(String(50), nullable=False)
    selection2 = Column(String(100), nullable=False)
    odds2_american = Column(Integer)
    odds2_decimal = Column(Float, nullable=False)
    line2 = Column(Float)
    
    book3 = Column(String(50))
    selection3 = Column(String(100))
    odds3_american = Column(Integer)
    odds3_decimal = Column(Float)
    
    profit_pct = Column(Float, nullable=False)
    stake1_pct = Column(Float)
    stake2_pct = Column(Float)
    stake3_pct = Column(Float)
    middle_size = Column(Float)
    combined_hold = Column(Float)
    
    detected_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('game_id', 'market_type', 'book1', 'book2', 'book3', 
                         'selection1', 'selection2', 'selection3', 'line1', 'line2', 
                         name='uq_arb_opp'),
        Index('idx_active_arbs', 'is_active'),
    )
