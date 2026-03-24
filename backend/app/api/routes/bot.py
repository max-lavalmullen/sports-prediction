"""
Bot Management API Endpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.services.bot.paper_bot import PaperTradingBot

router = APIRouter()


class BotStatus(BaseModel):
    bot_id: str
    bot_type: str
    is_active: bool
    balance: float
    active_bets_count: int


class BotLog(BaseModel):
    id: str
    action: str
    game_id: Optional[int]
    selection: Optional[str]
    stake: Optional[float]
    odds: Optional[float]
    status: str
    executed_at: datetime


@router.get("/status", response_model=BotStatus)
async def get_bot_status(
    bot_id: str = "paper_default",
    db: AsyncSession = Depends(get_db)
):
    """Get the current status of a bot."""
    bot = PaperTradingBot(bot_id=bot_id)
    balance = bot.get_balance()

    # Count active (unsettled) bets for this bot
    from app.models.bot import BotExecution
    result = await db.execute(
        select(func.count(BotExecution.id)).where(
            BotExecution.bot_id == bot_id,
            BotExecution.status == 'placed'
        )
    )
    active_count = result.scalar() or 0

    return BotStatus(
        bot_id=bot_id,
        bot_type="paper",
        is_active=True,
        balance=balance,
        active_bets_count=active_count
    )


@router.get("/logs", response_model=List[BotLog])
async def get_bot_logs(
    bot_id: str = "paper_default",
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get execution logs for a bot."""
    from app.models.bot import BotExecution

    result = await db.execute(
        select(BotExecution)
        .where(BotExecution.bot_id == bot_id)
        .order_by(BotExecution.executed_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        BotLog(
            id=str(log.id),
            action=log.action or "unknown",
            game_id=log.game_id,
            selection=log.selection,
            stake=float(log.stake) if log.stake else None,
            odds=float(log.odds) if log.odds else None,
            status=log.status or "unknown",
            executed_at=log.executed_at or datetime.utcnow()
        )
        for log in logs
    ]


@router.post("/start")
async def start_bot(bot_id: str = "paper_default"):
    """Start a bot (mark as active)."""
    # In a real implementation, this would spawn a background task
    return {"status": "started", "bot_id": bot_id}


@router.post("/stop")
async def stop_bot(bot_id: str = "paper_default"):
    """Stop a bot (mark as inactive)."""
    return {"status": "stopped", "bot_id": bot_id}
