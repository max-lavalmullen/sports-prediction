"""
Quick test script for data APIs.
Run: python3 test_data_apis.py
"""

import sys
sys.path.insert(0, '.')

print("=" * 60)
print("Testing Sports Data APIs")
print("=" * 60)

# Test NBA API
print("\n1. Testing NBA API...")
try:
    from data.apis.nba_data import NBADataFetcher, NBA_API_AVAILABLE
    if NBA_API_AVAILABLE:
        nba = NBADataFetcher()
        # Get today's games
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        games = nba.get_games_by_date(today)
        print(f"   ✓ NBA API working - Found {len(games) if not games.empty else 0} games scheduled today")

        # Get standings
        standings = nba.get_standings()
        print(f"   ✓ NBA standings - {len(standings)} teams")
    else:
        print("   ✗ nba_api package not available")
except Exception as e:
    print(f"   ✗ NBA API error: {e}")

# Test NFL API
print("\n2. Testing NFL API...")
try:
    from data.apis.nfl_data import NFLDataFetcher, NFL_DATA_AVAILABLE
    if NFL_DATA_AVAILABLE:
        nfl = NFLDataFetcher()
        # Get 2024 schedule
        schedules = nfl.get_schedules([2024])
        print(f"   ✓ NFL API working - Found {len(schedules)} games in 2024 schedule")

        # Get betting lines
        lines = nfl.get_betting_lines([2024])
        print(f"   ✓ NFL betting lines - {len(lines)} games with lines")
    else:
        print("   ✗ nfl_data_py package not available")
except Exception as e:
    print(f"   ✗ NFL API error: {e}")

# Test MLB API
print("\n3. Testing MLB API...")
try:
    from data.apis.mlb_data import MLBDataFetcher, PYBASEBALL_AVAILABLE
    if PYBASEBALL_AVAILABLE:
        mlb = MLBDataFetcher()
        # Get team schedule (using Yankees as test)
        schedule = mlb.get_team_schedule(2024, "NYY")
        print(f"   ✓ MLB API working - NYY 2024: {len(schedule)} games")
    else:
        print("   ✗ pybaseball package not available")
except Exception as e:
    print(f"   ✗ MLB API error: {e}")

# Test Unified Stats Service
print("\n4. Testing Unified Stats Service...")
try:
    from data.apis.stats_service import stats_service
    print(f"   ✓ Available sports: {stats_service.available_sports}")
except Exception as e:
    print(f"   ✗ Stats service error: {e}")

# Test Odds API (if configured)
print("\n5. Testing Odds API...")
try:
    import os
    import asyncio
    import httpx

    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        # Try loading from .env
        env_path = "/Users/maxl/Desktop/sports model/backend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("ODDS_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if api_key and api_key != "your_odds_api_key_here":
        async def test_odds():
            url = "https://api.the-odds-api.com/v4/sports"
            params = {"apiKey": api_key}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10.0)
                return resp.json()

        sports = asyncio.run(test_odds())
        print(f"   ✓ Odds API working - {len(sports)} sports available")

        # Show key sports
        key_sports = [s for s in sports if s['key'] in ['basketball_nba', 'americanfootball_nfl', 'baseball_mlb']]
        for s in key_sports:
            print(f"      - {s['title']}: active={s.get('active', 'N/A')}")
    else:
        print("   ⚠ ODDS_API_KEY not configured (set in .env file)")
except Exception as e:
    print(f"   ✗ Odds API error: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)