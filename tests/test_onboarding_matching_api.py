from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.main import app
from app.models.user import User
from app.services import onboarding_service


def _make_client_and_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, TestingSessionLocal


def _create_user(db: Session, *, nickname: str, user_id: str, instrument: str = "guitar") -> User:
    user = User(
        nickname=nickname,
        user_id=user_id,
        hashed_password=hash_password("pw1234"),
        instrument=instrument,
    )
    db.add(user)
    db.flush()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


def test_personal_onboarding_upsert_makes_user_visible_in_recruit_matching(monkeypatch) -> None:
    monkeypatch.setattr(
        onboarding_service,
        "generate_profile_summary",
        lambda **_: "온보딩 요약 문장입니다.",
    )

    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        viewer = _create_user(db, nickname="viewer", user_id="viewer")
        candidate = _create_user(db, nickname="candidate", user_id="candidate", instrument="drum")
        db.commit()
        viewer_headers = _auth_headers(viewer)
        candidate_headers = _auth_headers(candidate)

    personal_payload = {
        "instruments": ["guitar"],
        "parts": ["lead"],
        "genres": ["rock", "indie"],
        "region": "Seoul Hongdae",
        "availability": ["weekday_evening", "weekend_day"],
        "practiceFrequency": "weekly_1",
        "activityGoal": {"activityGoals": ["band"]},
    }
    resp = client.post("/api/onboarding/personal", json=personal_payload, headers=viewer_headers)
    assert resp.status_code == 200, resp.text

    candidate_payload = {
        "instruments": ["drum"],
        "parts": ["main"],
        "genres": ["rock", "indie"],
        "region": "Seoul Hongdae",
        "availability": ["weekday_evening"],
        "practiceFrequency": "weekly_1",
        "activityGoal": {"activityGoals": ["band"]},
    }
    resp = client.post("/api/onboarding/personal", json=candidate_payload, headers=candidate_headers)
    assert resp.status_code == 200, resp.text

    match_resp = client.post(
        "/api/matching/match",
        json={
            "profile": {},
            "mode": "recruit",
            "min_score": 0,
            "limit": 10,
            "hard_filters": {"same_instrument": False, "same_region": False},
            "recruit_needs": [{"instrument": "drum", "part": "main", "count": 1, "required": False}],
        },
        headers=viewer_headers,
    )
    assert match_resp.status_code == 200, match_resp.text
    results = match_resp.json()["results"]
    nicknames = [row["nickname"] for row in results]
    assert "candidate" in nicknames
    candidate_row = next(row for row in results if row["nickname"] == "candidate")
    assert candidate_row["ai_summary"] == "온보딩 요약 문장입니다."

    app.dependency_overrides.clear()


def test_team_onboarding_upsert_makes_team_visible_in_apply_matching(monkeypatch) -> None:
    monkeypatch.setattr(
        onboarding_service,
        "generate_profile_summary",
        lambda **_: "개인 요약 문장입니다.",
    )
    monkeypatch.setattr(
        onboarding_service,
        "generate_team_recruit_summary",
        lambda **_: "팀 모집 요약 문장입니다.",
    )

    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        applicant = _create_user(db, nickname="applicant", user_id="applicant", instrument="vocal")
        leader = _create_user(db, nickname="leader", user_id="leader", instrument="guitar")
        db.commit()
        applicant_headers = _auth_headers(applicant)
        leader_headers = _auth_headers(leader)

    applicant_onboarding = client.post(
        "/api/onboarding/personal",
        json={
            "instruments": ["vocal"],
            "parts": ["main"],
            "genres": ["pop", "rock"],
            "region": "Seoul Hongdae",
            "availability": ["weekday_evening"],
            "practiceFrequency": "weekly_1",
            "activityGoal": {"activityGoals": ["band"]},
        },
        headers=applicant_headers,
    )
    assert applicant_onboarding.status_code == 200, applicant_onboarding.text

    leader_onboarding = client.post(
        "/api/onboarding/personal",
        json={
            "instruments": ["guitar"],
            "parts": ["lead"],
            "genres": ["pop", "rock"],
            "region": "Seoul Hongdae",
            "availability": ["weekday_evening"],
            "practiceFrequency": "weekly_1",
            "activityGoal": {"activityGoals": ["band"]},
            "style": "balanced",
        },
        headers=leader_headers,
    )
    assert leader_onboarding.status_code == 200, leader_onboarding.text

    create_team_resp = client.post(
        "/api/team/create",
        json={
            "team_name": "hongdae-pop-rock",
            "description": "practice band",
            "leader_nickname": "leader",
            "members": [],
            "average_age": "20s",
            "region": "Seoul Hongdae",
            "genres": ["pop", "rock"],
            "gender_ratio": "mixed",
            "reference_songs": ["Song A"],
        },
    )
    assert create_team_resp.status_code == 201, create_team_resp.text
    team_id = create_team_resp.json()["team_id"]

    team_onboarding_resp = client.post(
        f"/api/onboarding/team/{team_id}",
        json={
            "teamProfile": {
                "genres": ["pop", "rock"],
                "region": "Seoul Hongdae",
                "practiceFrequency": "weekly_1",
                "averageAge": "20s",
                "activityGoal": {"activityGoals": ["performance"]},
                "recruitingSessions": ["vocal"],
            },
            "recruit_needs": [{"instrument": "vocal", "part": "main", "count": 1, "required": True}],
        },
        headers=leader_headers,
    )
    assert team_onboarding_resp.status_code == 200, team_onboarding_resp.text

    match_resp = client.post(
        "/api/matching/match",
        json={
            "profile": {},
            "mode": "apply",
            "min_score": 0,
            "limit": 10,
            "hard_filters": {"same_instrument": False, "same_region": False},
            "recruit_needs": [],
        },
        headers=applicant_headers,
    )
    assert match_resp.status_code == 200, match_resp.text
    results = match_resp.json()["results"]
    nicknames = [row["nickname"] for row in results]
    assert "hongdae-pop-rock" in nicknames
    team_row = next(row for row in results if row["nickname"] == "hongdae-pop-rock")
    assert team_row["ai_summary"] == "팀 모집 요약 문장입니다."

    app.dependency_overrides.clear()
