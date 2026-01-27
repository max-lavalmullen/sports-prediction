from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from app.core.database import Base
from datetime import datetime

class SGPCorrelation(Base):
    __tablename__ = "sgp_correlations"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(50), nullable=False)
    leg1_type = Column(String(50), nullable=False)
    leg2_type = Column(String(50), nullable=False)
    correlation_coefficient = Column(Float, nullable=False)
    sample_size = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('sport', 'leg1_type', 'leg2_type', name='uq_sgp_corr'),
    )
