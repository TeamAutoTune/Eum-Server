from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.models.team import Team, TeamInvite, TeamMember
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


def _create_team(db: Session, team_name: str, leader: User, members: list[User]) -> Team:
    team = Team(team_name=team_name, description="desc", leader_id=leader.id)
    db.add(team)
    db.flush()

    db.add(TeamMember(team_id=team.id, user_id=leader.id, role="leader"))
    for member in members:
        db.add(TeamMember(team_id=team.id, user_id=member.id, role="member"))
    db.commit()
    db.refresh(team)
    return team


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


def test_team_invite_success_by_nickname() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader1", "leader1")
        target = _create_user(db, "target1", "target1")
        team = _create_team(db, "band-a", leader, [])
        team_id = team.id
        leader_id = leader.id
        target_id = target.id

    app.dependency_overrides[get_current_user] = lambda: User(
        id=leader_id,
        nickname="leader1",
        user_id="leader1",
        hashed_password="test-hash",
        instrument="guitar",
    )

    resp = client.post(f"/api/team/{team_id}/invite", json={"nickname": " target1 "})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "team_id": team_id,
        "invited_user_id": target_id,
        "invited_nickname": "target1",
        "status": "invited",
    }

    with SessionLocal() as db:
        invites = db.scalars(select(TeamInvite).where(TeamInvite.team_id == team_id)).all()
        assert len(invites) == 1
        assert invites[0].invited_user_id == target_id

    app.dependency_overrides.clear()


def test_team_invite_blocks_duplicate_and_existing_member() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader2", "leader2")
        member = _create_user(db, "member1", "member1")
        target = _create_user(db, "target2", "target2")
        team = _create_team(db, "band-b", leader, [member])
        team_id = team.id
        leader_id = leader.id
        target_id = target.id

    app.dependency_overrides[get_current_user] = lambda: User(
        id=leader_id,
        nickname="leader2",
        user_id="leader2",
        hashed_password="test-hash",
        instrument="guitar",
    )

    member_resp = client.post(f"/api/team/{team_id}/invite", json={"nickname": "member1"})
    assert member_resp.status_code == 400
    assert member_resp.json()["detail"] == "User is already a team member"

    first_resp = client.post(f"/api/team/{team_id}/invite", json={"user_id": target_id})
    assert first_resp.status_code == 200, first_resp.text

    duplicate_resp = client.post(f"/api/team/{team_id}/invite", json={"target_user_id": target_id})
    assert duplicate_resp.status_code == 400
    assert duplicate_resp.json()["detail"] == "User is already invited"

    app.dependency_overrides.clear()


def test_team_invite_blocks_non_leader() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader3", "leader3")
        member = _create_user(db, "member2", "member2")
        target = _create_user(db, "target3", "target3")
        team = _create_team(db, "band-c", leader, [member])
        team_id = team.id
        member_id = member.id
        target_nickname = target.nickname

    app.dependency_overrides[get_current_user] = lambda: User(
        id=member_id,
        nickname="member2",
        user_id="member2",
        hashed_password="test-hash",
        instrument="guitar",
    )

    resp = client.post(f"/api/team/{team_id}/invite", json={"nickname": target_nickname})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Only team leaders can invite users"

    app.dependency_overrides.clear()
