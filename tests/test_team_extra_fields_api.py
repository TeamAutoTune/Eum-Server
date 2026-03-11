from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models.user import User


def _create_user(db: Session, nickname: str, user_id: str) -> User:
    user = User(
        nickname=nickname,
        user_id=user_id,
        hashed_password="test-hash",
        instrument="guitar",
    )
    db.add(user)
    db.flush()
    return user


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


def test_create_team_with_extra_fields_and_detail_response() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        _create_user(db, "leader-a", "leader-a")
        _create_user(db, "member-a", "member-a")
        _create_user(db, "member-b", "member-b")
        db.commit()

    payload = {
        "team_name": "홍대밴드",
        "description": "주말 합주팀",
        "leader": "leader-a",
        "members": ["member-a", "member-b"],
        "average_age": "20대",
        "region": "서울",
        "genres": ["록 (Rock)", "인디 (Indie)"],
        "gender_ratio": "혼성",
        "reference_songs": [
            "Radiohead - Creep",
            "Oasis - Wonderwall",
        ],
    }
    create_resp = client.post("/api/team/create", json=payload)
    assert create_resp.status_code == 201, create_resp.text
    create_body = create_resp.json()

    assert set(create_body.keys()) == {"team_id", "team_name", "leader", "members"}
    assert create_body["team_name"] == "홍대밴드"
    assert create_body["leader"] == "leader-a"

    team_id = create_body["team_id"]

    detail_resp = client.get(f"/api/team/{team_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    detail_body = detail_resp.json()
    assert detail_body["average_age"] == "20대"
    assert detail_body["region"] == "서울"
    assert detail_body["genres"] == ["록 (Rock)", "인디 (Indie)"]
    assert detail_body["gender_ratio"] == "혼성"
    assert detail_body["reference_songs"] == ["Radiohead - Creep", "Oasis - Wonderwall"]

    list_resp = client.get("/api/team/list")
    assert list_resp.status_code == 200, list_resp.text
    list_body = list_resp.json()
    assert len(list_body) == 1
    assert list_body[0]["average_age"] == "20대"
    assert list_body[0]["genres"] == ["록 (Rock)", "인디 (Indie)"]

    my_resp = client.get("/api/team/my", params={"nickname": "leader-a"})
    assert my_resp.status_code == 200, my_resp.text
    my_body = my_resp.json()
    assert my_body["has_team"] is True
    assert my_body["team"]["reference_songs"] == ["Radiohead - Creep", "Oasis - Wonderwall"]

    app.dependency_overrides.clear()


def test_create_team_extra_fields_missing_or_null_are_safe() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        _create_user(db, "leader-b", "leader-b")
        db.commit()

    create_resp = client.post(
        "/api/team/create",
        json={
            "team_name": "minimal-team",
            "description": "",
            "leader_nickname": "leader-b",
            "members": [],
            "genres": None,
            "reference_songs": None,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    team_id = create_resp.json()["team_id"]

    detail_resp = client.get(f"/api/team/{team_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()
    assert body["average_age"] == ""
    assert body["region"] == ""
    assert body["genres"] == []
    assert body["gender_ratio"] == ""
    assert body["reference_songs"] == []

    app.dependency_overrides.clear()
