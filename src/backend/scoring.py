"""Match scoring logic and group-standings computation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from itertools import combinations

from backend.database.models import Match


# ---------------------------------------------------------------------------
# Match-winner determination
# ---------------------------------------------------------------------------

def determine_match_winner(match: Match) -> uuid.UUID | None:
    """Return the winner's participant id, or *None* for a draw.

    Rules (applied in order):
    1. Ippon → immediate win.
    2. Two or more waza-ari → equivalent to ippon.
    3. Compare weighted score: waza-ari×10 + yuko×1.
    """
    if match.score_a_ippon >= 1 and match.score_b_ippon == 0:
        return match.participant_a_id
    if match.score_b_ippon >= 1 and match.score_a_ippon == 0:
        return match.participant_b_id
    if match.score_a_wazari >= 2 and match.score_b_wazari < 2:
        return match.participant_a_id
    if match.score_b_wazari >= 2 and match.score_a_wazari < 2:
        return match.participant_b_id

    total_a = match.score_a_wazari * 10 + match.score_a_yuko
    total_b = match.score_b_wazari * 10 + match.score_b_yuko
    if total_a > total_b:
        return match.participant_a_id
    if total_b > total_a:
        return match.participant_b_id
    return None


def is_instant_win(match: Match) -> bool:
    """True when the current scores already decide a winner (ippon / 2 waza-ari)."""
    return (
        match.score_a_ippon >= 1
        or match.score_b_ippon >= 1
        or match.score_a_wazari >= 2
        or match.score_b_wazari >= 2
    )


# ---------------------------------------------------------------------------
# Group standings
# ---------------------------------------------------------------------------

def compute_group_standings(matches: list[Match]) -> list[dict]:
    """Build a ranked standings table from completed matches.

    Returns a list of dicts sorted by points (desc), then wins (desc)::

        {"participant_id": ..., "wins": 2, "losses": 0, "draws": 0, "points": 20}

    Scoring: win = 10 pts, draw = 5 pts, loss = 0 pts.
    """
    stats: dict[uuid.UUID, dict] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "draws": 0, "points": 0}
    )

    for m in matches:
        if not m.completed:
            continue
        a, b = m.participant_a_id, m.participant_b_id
        # Ensure both appear even with 0-0 records
        _ = stats[a], stats[b]
        if m.winner_id == a:
            stats[a]["wins"] += 1
            stats[b]["losses"] += 1
            stats[a]["points"] += 10
        elif m.winner_id == b:
            stats[b]["wins"] += 1
            stats[a]["losses"] += 1
            stats[b]["points"] += 10
        else:
            stats[a]["draws"] += 1
            stats[b]["draws"] += 1
            stats[a]["points"] += 5
            stats[b]["points"] += 5

    standings = [{"participant_id": pid, **s} for pid, s in stats.items()]
    standings.sort(key=lambda x: (-x["points"], -x["wins"]))
    return standings


# ---------------------------------------------------------------------------
# Match generation
# ---------------------------------------------------------------------------

def generate_round_robin_matches(
    group_id: uuid.UUID,
    participant_ids: list[uuid.UUID],
) -> list[Match]:
    """Create all pairwise matches for a round-robin group."""
    return [
        Match(group_id=group_id, participant_a_id=a, participant_b_id=b)
        for a, b in combinations(participant_ids, 2)
    ]
