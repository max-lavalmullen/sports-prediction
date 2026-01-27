"""
Simple mock server for frontend development.
Run with: python mock_server.py
No database or Redis required.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import random
import uvicorn

app = FastAPI(title="Sports Prediction Mock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sample data
TEAMS = {
    "nba": [
        ("Los Angeles Lakers", "Golden State Warriors"),
        ("Boston Celtics", "Miami Heat"),
        ("Denver Nuggets", "Phoenix Suns"),
        ("Milwaukee Bucks", "Philadelphia 76ers"),
        ("Dallas Mavericks", "Oklahoma City Thunder"),
    ],
    "nfl": [
        ("Kansas City Chiefs", "San Francisco 49ers"),
        ("Buffalo Bills", "Miami Dolphins"),
        ("Dallas Cowboys", "Philadelphia Eagles"),
        ("Detroit Lions", "Green Bay Packers"),
    ],
    "mlb": [
        ("Los Angeles Dodgers", "Atlanta Braves"),
        ("New York Yankees", "Boston Red Sox"),
        ("Houston Astros", "Texas Rangers"),
    ],
    "soccer": [
        ("Manchester City", "Liverpool"),
        ("Real Madrid", "Barcelona"),
        ("Bayern Munich", "Borussia Dortmund"),
        ("PSG", "Marseille"),
    ],
}


def generate_games(sport: str, date: str):
    """Generate mock games for a sport."""
    games = []
    teams = TEAMS.get(sport, TEAMS["nba"])

    for i, (home, away) in enumerate(teams):
        hour = 12 + (i * 3)
        games.append({
            "id": f"{sport}_{date}_{i}",
            "sport": sport,
            "homeTeam": home,
            "awayTeam": away,
            "scheduledTime": f"{date}T{hour:02d}:00:00",
            "predictions": {
                "spread": {
                    "prediction": {
                        "predictedSpread": round(random.uniform(-10, 10), 1),
                        "confidence": round(random.uniform(0.55, 0.75), 2),
                    }
                },
                "total": {
                    "prediction": {
                        "predictedTotal": round(random.uniform(200, 240), 1) if sport == "nba" else round(random.uniform(40, 55), 1),
                    }
                },
                "moneyline": {
                    "prediction": {
                        "homeWinProb": round(random.uniform(0.4, 0.65), 2),
                    }
                }
            }
        })
    return games


def generate_value_bets(sport: str = None, min_edge: float = 0.03, limit: int = 10):
    """Generate mock value bets."""
    bets = []
    sports = [sport] if sport else ["nba", "nfl", "mlb", "soccer"]

    selections = [
        ("Lakers -4.5", "spread", "nba"),
        ("Chiefs ML", "moneyline", "nfl"),
        ("Celtics/Heat Over 218.5", "total", "nba"),
        ("Cowboys +3.5", "spread", "nfl"),
        ("Dodgers ML", "moneyline", "mlb"),
        ("Man City -1.5", "spread", "soccer"),
        ("Real Madrid ML", "moneyline", "soccer"),
        ("Yankees/Red Sox Under 8.5", "total", "mlb"),
        ("Nuggets -6.5", "spread", "nba"),
        ("Bills ML", "moneyline", "nfl"),
    ]

    for selection, pred_type, s in selections:
        if sport and s != sport:
            continue
        edge = round(random.uniform(0.03, 0.12), 3)
        if edge >= min_edge:
            bets.append({
                "gameId": f"{s}_game_{random.randint(1, 100)}",
                "selection": selection,
                "predictionType": pred_type,
                "edge": edge,
                "ourProb": round(random.uniform(0.52, 0.68), 2),
                "marketOdds": random.choice([-110, -115, -105, +105, +110, -120]),
                "sport": s,
            })

    return sorted(bets, key=lambda x: x["edge"], reverse=True)[:limit]


@app.get("/api/v1/predictions")
async def get_predictions(sport: str = None, date: str = None):
    """Get predictions for games."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    if sport:
        return generate_games(sport, date)

    all_games = []
    for s in TEAMS.keys():
        all_games.extend(generate_games(s, date))
    return all_games


@app.get("/api/v1/predictions/value")
async def get_value_bets(sport: str = None, min_edge: float = 0.03, limit: int = 10):
    """Get value betting opportunities."""
    return generate_value_bets(sport, min_edge, limit)


@app.get("/api/v1/bets/stats")
async def get_bet_stats():
    """Get betting statistics."""
    return {
        "totalProfit": round(random.uniform(1500, 3500), 2),
        "roi": round(random.uniform(0.06, 0.12), 3),
        "winRate": round(random.uniform(0.52, 0.58), 3),
        "totalBets": random.randint(150, 300),
        "pendingBets": random.randint(3, 10),
        "avgEdge": round(random.uniform(0.04, 0.07), 3),
    }


@app.get("/api/v1/analytics/trends")
async def get_trends():
    """Get profitable trends."""
    return [
        {"trend": "Home favorites -3 to -7", "record": "45-32", "roi": 8.2, "sample": 77},
        {"trend": "Road underdogs +7 or more", "record": "28-19", "roi": 12.1, "sample": 47},
        {"trend": "Under in back-to-backs", "record": "38-22", "roi": 15.3, "sample": 60},
        {"trend": "Dog off a loss by 10+", "record": "22-15", "roi": 9.8, "sample": 37},
        {"trend": "Over in revenge games", "record": "18-11", "roi": 11.2, "sample": 29},
    ]


@app.get("/health")
async def health():
    return {"status": "healthy", "mock": True}


@app.get("/")
async def root():
    return {
        "name": "Sports Prediction Mock API",
        "version": "1.0.0",
        "mode": "mock",
        "docs": "/docs",
    }


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Mock API Server Starting")
    print("  Open http://localhost:8000/docs for API docs")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
