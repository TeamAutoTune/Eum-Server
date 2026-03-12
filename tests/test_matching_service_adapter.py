from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.matching_service import (
    _normalize_candidate_for_engine,
    _normalize_profile_for_engine,
    _team_to_profile_data,
)
from app.models.team import Team
from app.models.team_matching_profile import TeamMatchingProfile


def test_normalize_profile_for_engine_preserves_frontend_shape_and_derives_sessions() -> None:
    profile = {
        "instruments": ["guitar", "vocal"],
        "genres": ["rock", "indie"],
        "practiceFrequency": "weekly_2",
        "style": "balanced",
        "region": "서울",
        "ageGroup": "20대",
        "lifestyle": {
            "drink": "가끔 참여",
            "smoking": "비흡연",
            "social": "보통",
            "meal": "가끔 참여",
        },
        "activityGoal": {"activityGoals": ["band", "busking"]},
        "recruitNeeds": [
            {"instrument": "drum", "part": "main", "count": 1, "required": False},
        ],
    }

    normalized = _normalize_profile_for_engine(profile, {})

    assert normalized["instruments"] == ["guitar", "vocal"]
    assert normalized["playableInstruments"] == ["guitar", "vocal"]
    assert normalized["genres"] == ["rock", "indie"]
    assert normalized["goals"] == ["band", "busking"]
    assert normalized["recruitingSessions"] == ["drum"]
    assert normalized["performancePreferences"]["practiceFrequency"] == "weekly_2"


def test_normalize_candidate_for_engine_falls_back_to_existing_candidate_instruments() -> None:
    candidate = {
        "id": "user_1",
        "nickname": "tester",
        "instruments": ["bass"],
        "genres": ["rock"],
        "_profile_data": {
            "performancePreferences": {
                "practiceFrequency": "weekly_1",
                "performanceStyle": "balanced",
                "activityRegionSido": "Seoul",
            },
            "activityGoal": {"activityGoals": ["band"]},
        },
    }

    normalized = _normalize_candidate_for_engine(candidate)

    assert normalized["instruments"] == ["bass"]
    assert normalized["recruitingSessions"] == ["bass"]
    assert normalized["goals"] == ["band"]
    assert normalized["practiceFrequency"] == "weekly_1"


def test_normalize_profile_for_engine_accepts_nested_team_profile() -> None:
    profile = {
        "instruments": ["guitar"],
        "genres": ["rock"],
        "teamProfile": {
            "genres": ["jazz", "pop"],
            "practiceFrequency": "PRACTICE_3_PLUS",
            "averageAge": "AGE_30S",
            "region": "SEOUL",
            "recruitingSessions": ["DRUM"],
            "goals": ["GOAL_BAND_PROJECT"],
        },
        "leaderProfile": {
            "style": "STYLE_BALANCED",
            "lifestyle": {
                "drink": "DRINK_SOMETIMES",
                "smoking": "NON_SMOKING",
                "social": "SOCIAL_NORMAL",
                "meal": "MEAL_SOMETIMES",
            },
        },
    }

    normalized = _normalize_profile_for_engine(profile, {})

    assert normalized["genres"] == ["jazz", "pop"]
    assert normalized["practiceFrequency"] == "PRACTICE_3_PLUS"
    assert normalized["averageAge"] == "AGE_30S"
    assert normalized["recruitingSessions"] == ["DRUM"]
    assert normalized["style"] == "STYLE_BALANCED"


def test_team_to_profile_data_includes_teamprofile_ai_summary() -> None:
    team = Team(
        team_name="BandA",
        description="desc",
        average_age="AGE_20S",
        region="SEOUL",
        genres='["rock"]',
        gender_ratio="MIXED",
        reference_songs="[]",
        leader_id="leader-1",
    )
    team_matching_profile = TeamMatchingProfile(
        team_id=1,
        profile_data={"teamProfile": {"practiceFrequency": "PRACTICE_2"}},
        recruit_needs=[{"instrument": "DRUM", "part": "MAIN"}],
        recruit_summary="team recruit summary",
    )

    profile_data, _ = _team_to_profile_data(team, team_matching_profile)

    assert profile_data["teamProfile"]["ai_summary"] == "team recruit summary"
