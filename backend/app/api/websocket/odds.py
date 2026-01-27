"""
WebSocket endpoint for real-time odds streaming.
"""
import asyncio
import json
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


class OddsConnectionManager:
    """Manages WebSocket connections for odds streaming."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = {"sports": [], "markets": []}
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, sports: list, markets: list):
        """Update subscription preferences for a connection."""
        self.subscriptions[websocket] = {
            "sports": sports,
            "markets": markets
        }
        await websocket.send_json({
            "type": "subscribed",
            "sports": sports,
            "markets": markets
        })

    async def broadcast_odds(self, odds_update: dict):
        """Send odds update to all relevant subscribers."""
        sport = odds_update.get("sport")
        market = odds_update.get("market_type")

        for connection in self.active_connections.copy():
            try:
                sub = self.subscriptions.get(connection, {})
                sports = sub.get("sports", [])
                markets = sub.get("markets", [])

                # Send if subscribed to this sport/market or subscribed to all
                if (not sports or sport in sports) and (not markets or market in markets):
                    await connection.send_json(odds_update)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                self.disconnect(connection)


manager = OddsConnectionManager()


@router.websocket("/odds")
async def websocket_odds(websocket: WebSocket):
    """
    WebSocket endpoint for real-time odds streaming.

    Clients can subscribe to specific sports and markets.
    Send: {"action": "subscribe", "sports": ["nba", "nfl"], "markets": ["spread", "total"]}
    Receive: {"type": "odds_update", "game_id": 123, "sportsbook": "DraftKings", ...}
    """
    await manager.connect(websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    sports = message.get("sports", [])
                    markets = message.get("markets", [])
                    await manager.subscribe(websocket, sports, markets)

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def push_odds_update(odds_data: dict):
    """
    Called by the odds service when new odds are received.
    Pushes to all connected WebSocket clients.
    """
    await manager.broadcast_odds({
        "type": "odds_update",
        **odds_data
    })
