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


def test_auth_count_returns_user_count() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        _create_user(db, "count1", "count1")
        _create_user(db, "count2", "count2")
        _create_user(db, "count3", "count3")
        db.commit()

    resp = client.get("/api/auth/count")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"count": 3}

    app.dependency_overrides.clear()


def test_auth_count_stats_splits_seed_and_heuristic_test_users() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        _create_user(db, "real-user", "guitarhero")
        _create_user(db, "Seed Nick (test)-001", "seed_test_001")
        _create_user(db, "demo-band", "user_demo_01")
        _create_user(db, "normal", "dummy_account")
        db.commit()

    resp = client.get("/api/auth/count-stats")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "total_users": 4,
        "seeded_test_users": 1,
        "heuristic_test_users": 2,
        "probable_real_signup_users": 1,
    }

    app.dependency_overrides.clear()
