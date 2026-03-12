from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.services import onboarding_service


def _make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _signup(client: TestClient, *, nickname: str, user_id: str, instrument: str) -> str:
    resp = client.post(
        "/api/auth/signup",
        json={
            "nickname": nickname,
            "user_id": user_id,
            "password": "pw1234",
            "instrument": instrument,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _personal_onboarding(client: TestClient, *, token: str, payload: dict) -> None:
    resp = client.post(
        "/api/onboarding/personal",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


def test_signup_onboarding_users_show_up_in_match_card_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        onboarding_service,
        "generate_profile_summary",
        lambda **_: "온보딩 한마디 요약입니다.",
    )

    client = _make_client()

    users = [
        {
            "nickname": "aaaaa",
            "user_id": "aaaaa_user",
            "instrument": "guitar",
            "onboarding": {
                "instruments": ["guitar"],
                "parts": ["lead"],
                "genres": ["rock", "indie"],
                "region": "Seoul Hongdae",
                "availability": ["weekday_evening", "weekend_day"],
                "practiceFrequency": "weekly_1",
                "activityGoal": {"activityGoals": ["band"]},
                "style": "balanced",
            },
        },
        {
            "nickname": "bbbbb",
            "user_id": "bbbbb_user",
            "instrument": "drum",
            "onboarding": {
                "instruments": ["drum"],
                "parts": ["main"],
                "genres": ["rock", "metal"],
                "region": "Seoul Hongdae",
                "availability": ["weekday_evening"],
                "practiceFrequency": "weekly_2",
                "activityGoal": {"activityGoals": ["performance"]},
                "style": "precise",
            },
        },
        {
            "nickname": "ccccc",
            "user_id": "ccccc_user",
            "instrument": "bass",
            "onboarding": {
                "instruments": ["bass"],
                "parts": ["rhythm"],
                "genres": ["rock", "pop"],
                "region": "Seoul Gangnam",
                "availability": ["weekend_day"],
                "practiceFrequency": "weekly_1",
                "activityGoal": {"activityGoals": ["hobby"]},
                "style": "balanced",
            },
        },
        {
            "nickname": "ddddd",
            "user_id": "ddddd_user",
            "instrument": "vocal",
            "onboarding": {
                "instruments": ["vocal"],
                "parts": ["main"],
                "genres": ["ballad", "pop"],
                "region": "Seoul Mapo",
                "availability": ["weekend_evening"],
                "practiceFrequency": "weekly_1",
                "activityGoal": {"activityGoals": ["busking"]},
                "style": "expressive",
            },
        },
        {
            "nickname": "eeeee",
            "user_id": "eeeee_user",
            "instrument": "keyboard",
            "onboarding": {
                "instruments": ["keyboard"],
                "parts": ["synth"],
                "genres": ["indie", "jazz"],
                "region": "Seoul Hongdae",
                "availability": ["weekday_night"],
                "practiceFrequency": "weekly_2",
                "activityGoal": {"activityGoals": ["band"]},
                "style": "balanced",
            },
        },
    ]

    token_by_nickname: dict[str, str] = {}
    for user in users:
        token = _signup(
            client,
            nickname=user["nickname"],
            user_id=user["user_id"],
            instrument=user["instrument"],
        )
        token_by_nickname[user["nickname"]] = token
        _personal_onboarding(
            client,
            token=token,
            payload=user["onboarding"],
        )

    viewer_token = token_by_nickname["aaaaa"]
    match_resp = client.post(
        "/api/matching/match",
        json={
            "profile": {},
            "mode": "recruit",
            "min_score": 0,
            "limit": 20,
            "hard_filters": {"same_instrument": False, "same_region": False},
            "recruit_needs": [
                {"instrument": "drum", "part": "", "count": 1, "required": False},
                {"instrument": "bass", "part": "", "count": 1, "required": False},
                {"instrument": "vocal", "part": "", "count": 1, "required": False},
                {"instrument": "keyboard", "part": "", "count": 1, "required": False},
            ],
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert match_resp.status_code == 200, match_resp.text
    results = match_resp.json()["results"]

    returned_nicknames = {row["nickname"] for row in results}
    expected_candidates = {"bbbbb", "ccccc", "ddddd", "eeeee"}
    assert expected_candidates.issubset(returned_nicknames)
    assert "aaaaa" not in returned_nicknames

    for row in results:
        if row["nickname"] not in expected_candidates:
            continue
        # MatchCard.js에서 바로 사용하는 핵심 필드가 채워져 있는지 검증
        assert isinstance(row.get("matchScore"), int)
        assert isinstance(row.get("reasons"), list)
        assert isinstance(row.get("instruments"), list) and len(row["instruments"]) > 0
        assert isinstance(row.get("parts"), list)
        assert isinstance(row.get("genres"), list) and len(row["genres"]) > 0
        assert isinstance(row.get("availability"), list)
        assert isinstance(row.get("region"), str) and row["region"]
        assert row.get("ai_summary") == "온보딩 한마디 요약입니다."

    app.dependency_overrides.clear()
