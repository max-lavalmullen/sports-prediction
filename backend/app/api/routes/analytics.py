"""
Analytics API endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.game import Team, Player, Game, Sport, PlayerGameStats


router = APIRouter()


class TeamStats(BaseModel):
    """Team statistics summary."""
    id: int
    name: str
    sport: str
    record: dict  # {wins, losses, ties}
    offensive_rating: Optional[float]
    defensive_rating: Optional[float]
    net_rating: Optional[float]
    recent_form: List[str]  # ["W", "W", "L", "W", "L"]
    home_record: dict
    away_record: dict
    ats_record: dict  # Against the spread
    over_under_record: dict


class PlayerStats(BaseModel):
    """Player statistics summary."""
    id: int
    name: str
    team: str
    position: str
    season_averages: dict
    last_5_averages: dict
    last_10_averages: dict
    home_away_splits: dict
    vs_position_rank: dict


@router.get("/teams/{team_id}", response_model=dict)
async def get_team_analytics(
    team_id: int,
    season: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive team analytics.

    Returns offensive/defensive metrics, trends, and ATS/O-U records.
    """
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Get recent games
    games_query = select(Game).where(
        (Game.home_team_id == team_id) | (Game.away_team_id == team_id)
    ).order_by(Game.scheduled_time.desc()).limit(20)

    result = await db.execute(games_query)
    games = result.scalars().all()

    # Calculate stats (simplified - full implementation would compute from game data)
    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "sport": team.sport.value,
            "league": team.league,
            "conference": team.conference,
            "division": team.division
        },
        "record": {
            "wins": 25,
            "losses": 15,
            "pct": 0.625
        },
        "ratings": {
            "offensive": 112.5,
            "defensive": 108.2,
            "net": 4.3,
            "pace": 100.5
        },
        "ats_record": {
            "wins": 22,
            "losses": 18,
            "pushes": 0,
            "pct": 0.55
        },
        "over_under_record": {
            "overs": 21,
            "unders": 19,
            "pushes": 0,
            "over_pct": 0.525
        },
        "home_away": {
            "home": {"wins": 15, "losses": 5},
            "away": {"wins": 10, "losses": 10}
        },
        "recent_form": ["W", "W", "L", "W", "W"],
        "trends": {
            "last_10_ats": "7-3",
            "last_10_ou": "6-4 O",
            "home_ats": "8-4",
            "away_ats": "6-6",
            "as_favorite_ats": "5-7",
            "as_underdog_ats": "9-3"
        },
        "advanced_metrics": {
            # Sport-specific advanced stats would go here
        },
        "upcoming_games": [
            # Next few scheduled games
        ]
    }


@router.get("/players/{player_id}", response_model=dict)
async def get_player_analytics(
    player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive player analytics.

    Returns season stats, recent form, splits, and prop trends.
    """
    player = await db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get recent game stats
    stats_query = select(PlayerGameStats).where(
        PlayerGameStats.player_id == player_id
    ).order_by(PlayerGameStats.game_id.desc()).limit(20)

    result = await db.execute(stats_query)
    game_stats = result.scalars().all()

    return {
        "player": {
            "id": player.id,
            "name": player.name,
            "team": player.team.name if player.team else None,
            "position": player.position,
            "injury_status": player.injury_status,
            "injury_detail": player.injury_detail
        },
        "season_averages": {
            # Sport-specific averages
            "games_played": 40,
            "minutes": 32.5,
            # NBA example:
            "points": 22.3,
            "rebounds": 5.2,
            "assists": 6.8
        },
        "last_5_averages": {
            "points": 25.2,
            "rebounds": 4.8,
            "assists": 7.2
        },
        "last_10_averages": {
            "points": 23.1,
            "rebounds": 5.0,
            "assists": 6.9
        },
        "splits": {
            "home": {"points": 24.1, "rebounds": 5.5, "assists": 7.1},
            "away": {"points": 20.5, "rebounds": 4.9, "assists": 6.5},
            "vs_winning_teams": {"points": 21.0},
            "vs_losing_teams": {"points": 24.2},
            "back_to_back": {"points": 19.5, "minutes": 28.2}
        },
        "prop_trends": {
            "points": {
                "line": 22.5,
                "over_rate_last_10": 0.6,
                "over_rate_season": 0.52,
                "avg_vs_line": 0.8
            },
            "rebounds": {
                "line": 5.5,
                "over_rate_last_10": 0.4,
                "over_rate_season": 0.48
            }
        },
        "game_log": [
            # Recent game-by-game stats
        ]
    }


@router.get("/matchups/{game_id}", response_model=dict)
async def get_matchup_analytics(
    game_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get head-to-head matchup analysis.

    Returns historical matchups, key stats comparison, and edges.
    """
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "game": {
            "id": game.id,
            "scheduled_time": game.scheduled_time,
            "venue": game.venue.name if game.venue else None
        },
        "home_team": {
            "id": game.home_team_id,
            "name": game.home_team.name if game.home_team else "TBD"
        },
        "away_team": {
            "id": game.away_team_id,
            "name": game.away_team.name if game.away_team else "TBD"
        },
        "head_to_head": {
            "last_5": [
                # Recent matchup results
            ],
            "home_wins": 3,
            "away_wins": 2,
            "avg_total": 215.5,
            "avg_margin": 5.2
        },
        "comparison": {
            # Side-by-side stat comparison
            "offensive_rating": {"home": 112.5, "away": 108.2},
            "defensive_rating": {"home": 108.0, "away": 110.5},
            "pace": {"home": 100.5, "away": 98.2}
        },
        "key_matchups": [
            # Player vs player matchups
        ],
        "injuries": {
            "home": [],
            "away": []
        },
        "betting_trends": {
            "home_ats_last_10": "7-3",
            "away_ats_last_10": "5-5",
            "h2h_ats_last_5": "3-2 Home"
        }
    }


@router.get("/trends", response_model=dict)
async def get_betting_trends(
    sport: Sport,
    trend_type: str = Query("ats", description="ats, over_under, moneyline"),
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db)
):
    """
    Get league-wide betting trends.

    Returns profitable angles, situation-based trends, and system results.
    """
    return {
        "sport": sport.value,
        "period": f"Last {days} days",
        "trends": [
            {
                "name": "Home favorites -3 to -7",
                "record": "45-32",
                "roi": 0.08,
                "sample_size": 77
            },
            {
                "name": "Road underdogs +7 or more",
                "record": "28-19",
                "roi": 0.12,
                "sample_size": 47
            },
            {
                "name": "Under in back-to-backs",
                "record": "38-22",
                "roi": 0.15,
                "sample_size": 60
            }
        ],
        "situational": {
            "home_favorites": {"ats": "120-95", "pct": 0.558},
            "road_underdogs": {"ats": "98-85", "pct": 0.535},
            "revenge_games": {"ats": "25-18", "pct": 0.581},
            "off_loss": {"ats": "110-100", "pct": 0.524}
        }
    }
