"""
Sports Prediction Platform - Main FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import predictions, props, backtest, bets, analytics, arbitrage, sgp, bot
from app.api.websocket import odds as ws_odds, alerts as ws_alerts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    logger.info("Starting Sports Prediction Platform...")
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down Sports Prediction Platform...")


app = FastAPI(
    title="Sports Prediction Platform",
    description="Real-time sports predictions for NFL, NBA, MLB, and Soccer",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routes
app.include_router(predictions.router, prefix="/api/v1/predictions", tags=["Predictions"])
app.include_router(props.router, prefix="/api/v1/props", tags=["Player Props"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtesting"])
app.include_router(bets.router, prefix="/api/v1/bets", tags=["Bet Tracking"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(arbitrage.router, prefix="/api/v1/arb", tags=["Arbitrage"])
app.include_router(sgp.router, prefix="/api/v1/sgp", tags=["Same-Game Parlay"])
app.include_router(bot.router, prefix="/api/v1/bot", tags=["Betting Bot"])

# WebSocket routes
app.include_router(ws_odds.router, prefix="/ws", tags=["WebSocket"])
app.include_router(ws_alerts.router, prefix="/ws", tags=["WebSocket"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Sports Prediction Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
