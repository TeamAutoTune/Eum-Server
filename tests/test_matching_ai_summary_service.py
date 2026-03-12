from __future__ import annotations

from app.core.config import settings
from app.services.matching_ai_summary_service import generate_profile_summary, generate_team_recruit_summary


def test_generate_profile_summary_uses_db_payload_fallback_when_llm_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    summary = generate_profile_summary(
        profile_data={
            "instruments": ["guitar"],
            "genres": ["rock"],
            "region": "Seoul Hongdae",
            "practiceFrequency": "weekly_1",
            "activityGoal": {"activityGoals": ["band"]},
        },
        candidate_data={},
    )

    assert isinstance(summary, str) and summary.strip()


def test_generate_team_summary_uses_db_payload_fallback_when_llm_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    summary = generate_team_recruit_summary(
        profile_data={
            "teamProfile": {
                "teamName": "HongdaeBand",
                "genres": ["rock"],
                "region": "Seoul Hongdae",
                "practiceFrequency": "weekly_1",
            }
        },
        recruit_needs=[{"instrument": "drum", "part": "main", "count": 1, "required": True}],
    )

    assert isinstance(summary, str) and summary.strip()
