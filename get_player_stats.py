"""
get_player_stats.py - Simple standalone script to get NFL player stats for a season using pyespn.

Usage:
    python get_player_stats.py                          # defaults: 2024 season, all positions
    python get_player_stats.py --season 2023            # specific season
    python get_player_stats.py --season 2024 --pos QB   # only quarterbacks
    python get_player_stats.py --player "Patrick Mahomes"  # search for a specific player
"""

import argparse
import sys
from pyespn import PYESPN

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_player_stats(season=2024, position_filter=None, player_name=None):
    """
    Fetch and display NFL player stats for a given season.

    Args:
        season (int): The NFL season year (e.g. 2024).
        position_filter (str): Optional position to filter by (QB, RB, WR, etc.).
        player_name (str): Optional player name to search for (case-insensitive partial match).
    """
    # 1. Initialize the ESPN NFL client
    print(f"Connecting to ESPN NFL API...")
    espn = PYESPN("nfl")

    # 2. Load rosters for the season (gives us Player objects on each team)
    print(f"Loading rosters for the {season} season...")
    espn.load_season_rosters(season=season)

    # 3. Walk every team's roster and pull historical stats for matching players
    results = []
    seen_ids = set()

    for team in espn.teams:
        roster = team.roster.get(season, [])
        for player in roster:
            pid = player.id
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)

            pos = getattr(player, "position_abbreviation", None)
            name = player.full_name or player.display_name or "Unknown"

            # Apply filters
            if position_filter and pos != position_filter.upper():
                continue
            if player_name and player_name.lower() not in name.lower():
                continue

            # Fetch historical stats (returns {year: [Stat, ...]} or nested dict)
            try:
                stats_dict = espn.get_players_historical_stats(player_id=pid)
            except Exception as e:
                print(f"  [!] Could not load stats for {name}: {e}")
                continue

            if not stats_dict:
                continue

            # Extract the stats list for the requested season
            season_stats = _extract_season_stats(stats_dict, season)
            if not season_stats:
                continue

            results.append({
                "name": name,
                "position": pos,
                "team": team.name,
                "stats": season_stats,
            })

    # 4. Print results
    if not results:
        print("\nNo matching players found.")
        return results

    print(f"\n{'='*70}")
    print(f" NFL Player Stats  -  {season} Season")
    print(f"{'='*70}")

    for p in sorted(results, key=lambda x: x["name"]):
        print(f"\n{p['name']}  ({p['position']})  -  {p['team']}")
        print("-" * 50)
        for stat in p["stats"]:
            print(f"  {stat['name']:30s}  {stat['value']}")

    print(f"\n{'='*70}")
    print(f"Total players: {len(results)}")
    return results


def _extract_season_stats(stats_dict, target_season):
    """
    Pull out the list of stats for a single season from the nested dict
    returned by get_players_historical_stats().
    """
    target_str = str(target_season)
    all_stats = []

    for year_key, year_data in stats_dict.items():
        # Flatten nested structures into a simple list of Stat objects
        stat_list = _flatten(year_data)

        # Check if any Stat in this group belongs to the target season
        belongs = False
        for s in stat_list:
            s_season = getattr(s, "season", None)
            if str(s_season) == target_str:
                belongs = True
                break

        # Fallback: use the dict key itself
        if not belongs and str(year_key) == target_str:
            belongs = True

        if belongs:
            all_stats.extend(stat_list)

    # Convert Stat objects to simple dicts
    return [
        {
            "name": getattr(s, "name", "?"),
            "value": getattr(s, "stat_value", "N/A"),
            "category": getattr(s, "category", ""),
        }
        for s in all_stats
        if getattr(s, "stat_value", None) is not None
    ]


def _flatten(data):
    """Recursively flatten nested dicts/lists into a flat list of Stat objects."""
    items = []
    if isinstance(data, list):
        items.extend(data)
    elif isinstance(data, dict):
        for v in data.values():
            items.extend(_flatten(v))
    return items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get NFL player stats via pyespn")
    parser.add_argument("--season", type=int, default=2024, help="Season year (default: 2024)")
    parser.add_argument("--pos", type=str, default=None, help="Position filter, e.g. QB, RB, WR")
    parser.add_argument("--player", type=str, default=None, help="Player name search (partial, case-insensitive)")
    args = parser.parse_args()

    get_player_stats(season=args.season, position_filter=args.pos, player_name=args.player)
