"""
WebSocket endpoint for value alerts.
"""
import asyncio
import json
from typing import Set, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


class AlertConnectionManager:
    """Manages WebSocket connections for value alerts."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.alert_preferences: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.alert_preferences[websocket] = {
            "min_edge": 0.03,
            "sports": [],
            "bet_types": []
        }
        logger.info(f"Alert client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.alert_preferences.pop(websocket, None)
        logger.info(f"Alert client disconnected. Total: {len(self.active_connections)}")

    async def update_preferences(self, websocket: WebSocket, preferences: dict):
        """Update alert preferences for a connection."""
        self.alert_preferences[websocket] = {
            "min_edge": preferences.get("min_edge", 0.03),
            "sports": preferences.get("sports", []),
            "bet_types": preferences.get("bet_types", [])
        }
        await websocket.send_json({
            "type": "preferences_updated",
            "preferences": self.alert_preferences[websocket]
        })

    async def send_alert(self, alert: dict):
        """Send alert to all relevant subscribers."""
        alert_type = alert.get("type", "value_alert")
        sport = alert.get("sport")
        bet_type = alert.get("bet_type", "h2h")
        edge = alert.get("edge", alert.get("profit_pct", 0))

        for connection in self.active_connections.copy():
            try:
                prefs = self.alert_preferences.get(connection, {})

                # Check if alert matches preferences
                min_edge = prefs.get("min_edge", 0.03)
                sports = prefs.get("sports", [])
                bet_types = prefs.get("bet_types", [])

                if edge < min_edge:
                    continue
                if sports and sport not in sports:
                    continue
                if bet_types and bet_type not in bet_types:
                    continue

                await connection.send_json(alert)

            except Exception as e:
                logger.error(f"Error sending alert: {e}")
                self.disconnect(connection)


alert_manager = AlertConnectionManager()


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for value bet and arbitrage alerts.

    Clients can configure alert preferences.
    Send: {"action": "configure", "min_edge": 0.05, "sports": ["nba"]}
    Receive: {"type": "value_alert", "game_id": 123, "bet_type": "spread", "edge": 0.06, ...}
    Receive: {"type": "arbitrage_alert", "profit_pct": 2.5, ...}
    """
    await alert_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "configure":
                    await alert_manager.update_preferences(websocket, message)

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)


async def push_value_alert(alert_data: dict):
    """
    Called when a value bet is detected.
    Pushes to all connected clients based on their preferences.
    """
    if "type" not in alert_data:
        alert_data["type"] = "value_alert"
    await alert_manager.send_alert(alert_data)


async def push_arbitrage_alert(alert_data: dict):
    """
    Called when an arbitrage opportunity is detected.
    """
    if "type" not in alert_data:
        alert_data["type"] = "arbitrage_alert"
    await alert_manager.send_alert(alert_data)
