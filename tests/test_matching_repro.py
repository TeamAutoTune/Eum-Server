from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _payload(mode: str = "apply") -> dict:
    base_profile = {
        "instruments": ["guitar"],
        "parts": ["lead"],
        "genres": ["rock", "indie", "pop"],
        "availability": ["weekday_evening", "weekend_day", "weekend_evening"],
        "region": "서울특별시 강남구",
        "practiceFrequency": "weekly_1",
        "activityGoal": {"activityGoals": ["band"]},
        "requiredConditions": [],
        "avoidConditions": [],
    }
    body = {
        "profile": base_profile,
        "mode": mode,
        "min_score": 0,
        "limit": 20,
        "hard_filters": {"same_instrument": False, "same_region": False},
        "recruit_needs": [],
    }
    if mode == "recruit":
        body["recruit_needs"] = [
            {"instrument": "guitar", "part": "lead", "count": 1, "required": False}
        ]
    return body


def test_matching_repro_apply_and_recruit() -> None:
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"user_id": "seed_test_001", "password": "seed1234"})
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for mode in ("apply", "recruit"):
        resp = client.post("/api/matching/match", json=_payload(mode), headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "ranking_version" in data
        assert isinstance(data.get("results"), list)

        top3 = [
            {"id": row.get("id"), "score": row.get("matchScore")}
            for row in data.get("results", [])[:3]
        ]
        print(
            f"[repro] mode={mode} status={resp.status_code} "
            f"ranking_version={data.get('ranking_version')} "
            f"results={len(data.get('results', []))} top3={top3}"
        )
