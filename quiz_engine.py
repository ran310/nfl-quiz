"""
quiz_engine.py — Generates quiz questions by comparing NFL player stats.
"""

import random
from data_loader import POSITION_STATS, STAT_DISPLAY_NAMES, STAT_QUESTION_WORD


def _group_players_by_position_season(player_data):
    """
    Group player records by (position, season) for efficient question generation.
    Returns dict: {(position, season): {stat_name: [list of player records with that stat]}}
    """
    index = {}
    for record in player_data:
        pos = record["position"]
        season = record["season"]
        key = (pos, season)
        if key not in index:
            index[key] = {}
        for stat_name, stat_val in record["stats"].items():
            if stat_name not in index[key]:
                index[key][stat_name] = []
            index[key][stat_name].append(record)
    return index


def generate_questions(num_questions, player_data):
    """
    Generate a list of quiz questions.

    Each question picks two players of the same position who both have
    data for the same stat in the same season, and asks which one had
    the higher value.

    Returns:
        list of dicts, each with:
            - player1: {name, headshot, id, team}
            - player2: {name, headshot, id, team}
            - stat_name: internal stat key
            - stat_display: human-readable stat name
            - question_word: "more" / "a higher" / "higher"
            - season: int
            - correct_answer: 1 or 2
            - player1_value: float
            - player2_value: float
    """
    index = _group_players_by_position_season(player_data)

    # Build a list of all valid (position, season, stat_name) combos that have 2+ players
    valid_combos = []
    for (pos, season), stat_dict in index.items():
        for stat_name, players in stat_dict.items():
            if len(players) >= 2:
                valid_combos.append((pos, season, stat_name))

    if not valid_combos:
        raise ValueError("Not enough player data to generate questions. Try rebuilding the cache.")

    questions = []
    used_pairs = set()
    max_attempts = num_questions * 10

    attempts = 0
    while len(questions) < num_questions and attempts < max_attempts:
        attempts += 1

        # Pick a random valid combo
        pos, season, stat_name = random.choice(valid_combos)
        players = index[(pos, season)][stat_name]

        # Pick 2 different players
        if len(players) < 2:
            continue

        p1, p2 = random.sample(players, 2)

        # Avoid duplicate pairs
        pair_key = tuple(sorted([p1["id"], p2["id"]])) + (stat_name, season)
        if pair_key in used_pairs:
            continue
        used_pairs.add(pair_key)

        val1 = p1["stats"][stat_name]
        val2 = p2["stats"][stat_name]

        # Skip if values are equal (no clear winner)
        if val1 == val2:
            continue

        correct = 1 if val1 > val2 else 2

        question = {
            "player1": {
                "name": p1["name"],
                "headshot": p1["headshot"],
                "id": p1["id"],
                "team": p1.get("team", ""),
            },
            "player2": {
                "name": p2["name"],
                "headshot": p2["headshot"],
                "id": p2["id"],
                "team": p2.get("team", ""),
            },
            "stat_name": stat_name,
            "stat_display": STAT_DISPLAY_NAMES.get(stat_name, stat_name),
            "question_word": STAT_QUESTION_WORD.get(stat_name, "more"),
            "season": season,
            "correct_answer": correct,
            "player1_value": val1,
            "player2_value": val2,
        }
        questions.append(question)

    return questions


def format_stat_value(stat_name, value):
    """Format a stat value for display (e.g. add commas, decimal places)."""
    if value is None:
        return "N/A"

    # Percentage stats
    if stat_name in ("completionPct",):
        return f"{value:.1f}%"

    # Per-attempt / per-game stats
    if stat_name in ("yardsPerRushAttempt", "yardsPerReception", "rushingYardsPerGame", "QBRating"):
        return f"{value:.1f}"

    # Integer stats (yards, TDs, etc.)
    try:
        int_val = int(value)
        return f"{int_val:,}"
    except (ValueError, TypeError):
        return str(value)
