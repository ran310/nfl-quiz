"""
data_loader.py - Fetches NFL player data from ESPN via pyespn and caches it locally.

Run this file directly to build/rebuild the cache:
    python data_loader.py

Or import load_data() to read from the existing cache.
"""

import json
import os
import sys
import time
from pyespn import PYESPN

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_data.json")

# Positions we care about
ALLOWED_POSITIONS = {"QB", "RB", "WR"}

# Stats to extract per position (these are the stat `name` fields from ESPN)
POSITION_STATS = {
    "QB": [
        "passingYards", "passingTouchdowns", "completions",
        "interceptions", "completionPct", "QBRating"
    ],
    "RB": [
        "rushingYards", "rushingTouchdowns", "rushingAttempts",
        "yardsPerRushAttempt", "rushingYardsPerGame"
    ],
    "WR": [
        "receivingYards", "receivingTouchdowns", "receptions",
        "receivingTargets", "yardsPerReception"
    ],
}

# Human-readable display names for stats
STAT_DISPLAY_NAMES = {
    "passingYards": "Passing Yards",
    "passingTouchdowns": "Passing TDs",
    "completions": "Completions",
    "interceptions": "Interceptions",
    "completionPct": "Completion %",
    "QBRating": "QB Rating",
    "rushingYards": "Rushing Yards",
    "rushingTouchdowns": "Rushing TDs",
    "rushingAttempts": "Rushing Attempts",
    "yardsPerRushAttempt": "Yards Per Rush",
    "rushingYardsPerGame": "Rushing Yards/Game",
    "receivingYards": "Receiving Yards",
    "receivingTouchdowns": "Receiving TDs",
    "receptions": "Receptions",
    "receivingTargets": "Receiving Targets",
    "yardsPerReception": "Yards Per Reception",
}

# Which stats should be compared with "more" vs could go either way
STAT_QUESTION_WORD = {
    "passingYards": "more",
    "passingTouchdowns": "more",
    "completions": "more",
    "interceptions": "more",
    "completionPct": "a higher",
    "QBRating": "a higher",
    "rushingYards": "more",
    "rushingTouchdowns": "more",
    "rushingAttempts": "more",
    "yardsPerRushAttempt": "higher",
    "rushingYardsPerGame": "higher",
    "receivingYards": "more",
    "receivingTouchdowns": "more",
    "receptions": "more",
    "receivingTargets": "more",
    "yardsPerReception": "higher",
}

SEASONS = [2024]


def _get_headshot_url(player):
    """Extract headshot URL from player object."""
    if hasattr(player, 'headshot') and player.headshot:
        if hasattr(player.headshot, 'ref') and player.headshot.ref:
            return player.headshot.ref
    # Fallback: ESPN CDN pattern
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{player.id}.png"


def _extract_stats_from_list(stat_list, desired_stat_names):
    """Extract specific stat values from a list of Stat objects."""
    result = {}
    for stat in stat_list:
        stat_name = getattr(stat, 'name', None)
        stat_val = getattr(stat, 'stat_value', None)
        if stat_name and stat_name in desired_stat_names and stat_val is not None:
            try:
                result[stat_name] = float(stat_val)
            except (ValueError, TypeError):
                pass
    return result


def build_cache():
    """Fetch player data from ESPN and save to cache file."""
    print("[*] Initializing ESPN NFL client...")
    espn = PYESPN('nfl')

    all_players = []
    seen_keys = set()

    for season in SEASONS:
        print(f"\n[*] Loading rosters for {season} season...")
        try:
            espn.load_season_rosters(season=season)
        except Exception as e:
            print(f"  [!] Error loading rosters for {season}: {e}")
            continue

        player_count = 0
        for team in espn.teams:
            roster = team.roster.get(season, [])
            for player in roster:
                pos = getattr(player, 'position_abbreviation', None)
                if pos not in ALLOWED_POSITIONS:
                    continue

                player_id = player.id
                if not player_id:
                    continue

                # Skip if we already processed this player
                # (stats are per-career, so one call covers all seasons)
                if player_id in seen_keys:
                    continue
                seen_keys.add(player_id)

                # Use the CLIENT-level method to get historical stats
                # (Player.load_player_historical_stats has a bug in pyespn)
                try:
                    stats_dict = espn.get_players_historical_stats(player_id=player_id)
                    print(f"[*] Loaded stats for {player.full_name} {player_id}")
                except Exception as e:
                    print(f"  [!] Could not load stats for {player.full_name} {player_id}: {e}")
                    continue

                if not stats_dict:
                    continue

                headshot_url = _get_headshot_url(player)
                desired_stats = POSITION_STATS.get(pos, [])

                # stats_dict is {year_str: {year_str: [list of Stat objects]}}
                # Build a mapping of season_year -> stat_list, processing
                # each inner year key separately so we don't merge years.
                year_stat_lists = {}

                for year_key, year_data in stats_dict.items():
                    if isinstance(year_data, dict):
                        # Each inner key may be a year with its own stat list
                        for inner_key, v in year_data.items():
                            if isinstance(v, list):
                                # inner_key is the year for these stats
                                try:
                                    yr = int(inner_key)
                                except (ValueError, TypeError):
                                    yr = None
                                if yr is None:
                                    # Try to read season from stat objects
                                    for s in v:
                                        if hasattr(s, 'season') and s.season:
                                            try:
                                                yr = int(s.season)
                                                break
                                            except (ValueError, TypeError):
                                                pass
                                if yr is not None:
                                    year_stat_lists.setdefault(yr, []).extend(v)
                            elif isinstance(v, dict):
                                # Another level of nesting
                                for inner_inner_key, vv in v.items():
                                    if isinstance(vv, list):
                                        try:
                                            yr = int(inner_inner_key)
                                        except (ValueError, TypeError):
                                            yr = None
                                        if yr is None:
                                            for s in vv:
                                                if hasattr(s, 'season') and s.season:
                                                    try:
                                                        yr = int(s.season)
                                                        break
                                                    except (ValueError, TypeError):
                                                        pass
                                        if yr is not None:
                                            year_stat_lists.setdefault(yr, []).extend(vv)
                    elif isinstance(year_data, list):
                        try:
                            yr = int(year_key)
                        except (ValueError, TypeError):
                            yr = None
                        if yr is None:
                            for s in year_data:
                                if hasattr(s, 'season') and s.season:
                                    try:
                                        yr = int(s.season)
                                        break
                                    except (ValueError, TypeError):
                                        pass
                        if yr is not None:
                            year_stat_lists.setdefault(yr, []).extend(year_data)

                # Now emit one record per season year
                for season_year, stat_list in year_stat_lists.items():
                    if season_year not in SEASONS:
                        continue

                    stats_extracted = _extract_stats_from_list(stat_list, desired_stats)
                    if not stats_extracted:
                        continue

                    player_record = {
                        "id": player_id,
                        "name": player.full_name or player.display_name or "Unknown",
                        "position": pos,
                        "team": team.name,
                        "headshot": headshot_url,
                        "season": season_year,
                        "stats": stats_extracted,
                    }
                    all_players.append(player_record)
                    player_count += 1

                # Small delay to be nice to the API
                time.sleep(0.05)

        print(f"  [+] Season {season} done - {player_count} new player-season records")

    print(f"\n[*] Total: {len(all_players)} player-season records")
    print(f"[*] Saving to {CACHE_FILE}...")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_players, f, indent=2)
    print("[+] Cache built successfully!")

    return all_players


def load_data():
    """Load player data from cache. Builds cache if it doesn't exist."""
    if not os.path.exists(CACHE_FILE):
        print("Cache not found, building it now (this takes a few minutes)...")
        return build_cache()

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[+] Loaded {len(data)} player-season records from cache")
    return data


if __name__ == "__main__":
    build_cache()
