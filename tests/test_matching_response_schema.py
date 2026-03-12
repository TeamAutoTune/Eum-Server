from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.matching import MatchingResultOut
from app.services.matching_service import _candidate_ai_summary


def test_matching_result_out_keeps_team_card_fields_and_ai_summary() -> None:
    payload = {
        "recommendation_id": "rec_1",
        "rank_position": 1,
        "id": "10",
        "nickname": "BandA",
        "team_name": "BandA",
        "teamProfile": {
            "genres": ["rock"],
            "region": "SEOUL",
            "averageAge": "AGE_20S",
            "practiceFrequency": "PRACTICE_2",
            "recruitingSessions": ["DRUM"],
        },
        "genres": ["rock"],
        "region": "SEOUL",
        "practiceFrequency": "PRACTICE_2",
        "averageAge": "AGE_20S",
        "recruitingSessions": ["DRUM"],
        "matchScore": 87,
        "reasons": ["genre_match"],
        "ai_summary": "test summary",
    }

    result = MatchingResultOut.model_validate(payload)

    assert result.teamProfile["genres"] == ["rock"]
    assert result.ai_summary == "test summary"


def test_matching_result_out_allows_null_ai_summary() -> None:
    payload = {
        "recommendation_id": "rec_2",
        "rank_position": 1,
        "id": "u1",
        "nickname": "UserA",
        "instruments": ["guitar"],
        "parts": ["lead"],
        "genres": ["indie"],
        "region": "SEOUL",
        "availability": ["weekday_evening"],
        "matchScore": 75,
        "reasons": [],
        "ai_summary": None,
    }

    result = MatchingResultOut.model_validate(payload)

    assert result.ai_summary is None


def test_candidate_ai_summary_uses_db_summary_by_mode() -> None:
    team_candidate = {"_recruit_summary": "team summary", "_profile_summary": "user summary"}
    user_candidate = {"_recruit_summary": "team summary", "_profile_summary": "user summary"}

    assert _candidate_ai_summary(team_candidate, "apply") == "team summary"
    assert _candidate_ai_summary(user_candidate, "recruit") == "user summary"


def test_candidate_ai_summary_falls_back_to_team_profile_summary() -> None:
    team_candidate = {
        "_recruit_summary": None,
        "teamProfile": {"ai_summary": "fallback team summary"},
    }

    assert _candidate_ai_summary(team_candidate, "apply") == "fallback team summary"
