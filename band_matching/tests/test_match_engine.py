from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from band_matching.match_engine import (
    get_top_matches,
    hard_filter,
    normalize_profile,
    score_recruit_mode,
)


def make_user_profile() -> dict:
    return {
        "id": "user_001",
        "nickname": "VocalUser",
        "playableInstruments": ["vocal", "guitar"],
        "preferredGenres": ["rock", "indie", "pop"],
        "performancePreferences": {
            "performanceStyle": "balanced",
            "activityRegionSido": "Seoul",
            "practiceFrequency": "weekly_2",
        },
        "activityGoal": {"activityGoals": ["band", "busking"]},
        "ageGroup": "20대",
        "lifestyle": {
            "drink": "가끔 참여",
            "smoking": "비흡연",
            "social": "보통",
            "meal": "가끔 참여",
        },
    }


def make_team_candidate(**overrides) -> dict:
    base = {
        "id": "team_001",
        "nickname": "IndieTeam",
        "type": "TEAM",
        "recruitingSessions": ["GUITAR", "DRUM"],
        "genres": ["ROCK", "INDIE"],
        "goals": ["GOAL_BAND_PROJECT"],
        "practiceFrequency": "PRACTICE_2",
        "style": "STYLE_BALANCED",
        "region": "SEOUL",
        "averageAge": "AGE_20S",
        "lifestyle": {
            "drink": "DRINK_SOMETIMES",
            "smoking": "NON_SMOKING",
            "social": "SOCIAL_NORMAL",
            "meal": "MEAL_SOMETIMES",
        },
    }
    base.update(overrides)
    return base


def make_team_profile() -> dict:
    return {
        "id": "team_010",
        "nickname": "RecruitTeam",
        "recruitingSessions": ["BASS", "DRUM"],
        "genres": ["ROCK", "POP"],
        "goals": ["GOAL_BAND_PROJECT", "GOAL_BUSKING_LIVE"],
        "practiceFrequency": "PRACTICE_2",
        "style": "STYLE_BALANCED",
        "region": "SEOUL",
        "averageAge": "AGE_30S",
        "lifestyle": {
            "drink": "DRINK_SOMETIMES",
            "smoking": "NON_SMOKING",
            "social": "SOCIAL_NORMAL",
            "meal": "MEAL_SOMETIMES",
        },
    }


def make_user_candidate(**overrides) -> dict:
    base = {
        "id": "user_010",
        "nickname": "BassUser",
        "instruments": ["BASS", "VOCAL"],
        "genres": ["ROCK", "BALLAD"],
        "goals": ["GOAL_BAND_PROJECT"],
        "practiceFrequency": "PRACTICE_2",
        "style": "STYLE_BALANCED",
        "region": "SEOUL",
        "ageGroup": "AGE_20S",
        "lifestyle": {
            "drink": "DRINK_SOMETIMES",
            "smoking": "NON_SMOKING",
            "social": "SOCIAL_NORMAL",
            "meal": "MEAL_SOMETIMES",
        },
    }
    base.update(overrides)
    return base


def test_normalize_profile_accepts_legacy_shape():
    normalized = normalize_profile(make_user_profile())
    assert normalized["instruments"] == ["VOCAL", "GUITAR"]
    assert normalized["genres"] == ["ROCK", "INDIE", "POP"]


def test_apply_mode_session_filter_uses_team_recruiting_sessions():
    passed, reason = hard_filter(make_user_profile(), make_team_candidate(), mode="apply")
    assert passed is True
    assert reason == "session_match"


def test_recruit_mode_session_filter_fails_when_no_overlap():
    passed, reason = hard_filter(make_team_profile(), make_user_candidate(instruments=["VOCAL"]), mode="recruit")
    assert passed is False
    assert reason == "session_mismatch"


def test_apply_mode_prefers_better_aligned_team():
    profile = make_user_profile()
    high = make_team_candidate(id="team_high")
    low = make_team_candidate(
        id="team_low",
        genres=["JAZZ"],
        goals=["GOAL_PRO"],
        practiceFrequency="PRACTICE_3_PLUS",
        style="STYLE_EXPRESSIVE",
        averageAge="AGE_40S",
    )
    rows = get_top_matches(profile, [low, high], mode="apply")
    assert rows[0]["id"] == "team_high"
    assert rows[0]["matchScore"] > rows[1]["matchScore"]


def test_recruit_mode_scores_candidate():
    scored = score_recruit_mode(make_team_profile(), make_user_candidate())
    assert scored["excluded"] is False
    assert scored["score"] > 0
