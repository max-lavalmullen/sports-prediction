import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.data_collection_service import _save_games_to_db
from data.apis.nba_data import NBADataFetcher

async def backfill():
    print("Initializing NBA Data Fetcher...")
    fetcher = NBADataFetcher()
    
    # Define date ranges
    # 2024-25 Season (Oct 22, 2024 - Present)
    ranges = [
        ("2024-10-22", datetime.now().strftime("%Y-%m-%d")),
        # Uncomment below for last season if needed (takes longer)
        # ("2023-10-24", "2024-04-14") 
    ]
    
    for start_date, end_date in ranges:
        print(f"\n--- Backfilling from {start_date} to {end_date} ---")
        
        # We chunk it by month to avoid massive memory usage and potential API timeouts
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current < end:
            chunk_end = min(current + timedelta(days=14), end)
            
            s_str = current.strftime("%Y-%m-%d")
            e_str = chunk_end.strftime("%Y-%m-%d")
            
            print(f"Fetching {s_str} to {e_str}...")
            
            try:
                # Get games with box scores
                games = fetcher.get_historical_games(s_str, e_str, include_box_scores=True)
                
                if games:
                    print(f"  Found {len(games)} games. Saving to DB...")
                    await _save_games_to_db("nba", games)
                    print(f"  Saved batch.")
                else:
                    print("  No games found in this period.")
                    
            except Exception as e:
                print(f"  Error in batch {s_str}-{e_str}: {e}")
            
            # Move to next chunk
            current = chunk_end + timedelta(days=1)
            
            # Be nice to the API
            await asyncio.sleep(1)

    print("\nBackfill Complete!")

if __name__ == "__main__":
    try:
        asyncio.run(backfill())
    except KeyboardInterrupt:
        print("\nBackfill stopped by user.")
    except Exception as e:
        print(f"\nFatal error: {e}")
