from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models.team import Team, TeamChecklist, TeamMember, TeamNotice, TeamSchedule
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


def test_leave_team_member_success() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader1", "leader1")
        member1 = _create_user(db, "member1", "member1")
        member2 = _create_user(db, "member2", "member2")
        team = _create_team(db, "band-a", leader, [member1, member2])
        team_id = team.id

    resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": "member1"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "team_deleted": False,
        "message": "팀에서 탈퇴했습니다.",
    }

    with SessionLocal() as db:
        members = db.scalars(
            select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.id.asc())
        ).all()
        roles_by_nickname = {member.user.nickname: member.role for member in members}
        assert "member1" not in roles_by_nickname
        assert roles_by_nickname == {"leader1": "leader", "member2": "member"}

    app.dependency_overrides.clear()


def test_leave_team_leader_with_transfer() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader2", "leader2")
        member1 = _create_user(db, "member3", "member3")
        member2 = _create_user(db, "member4", "member4")
        team = _create_team(db, "band-b", leader, [member1, member2])
        team_id = team.id

    resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": "leader2"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "team_deleted": False,
        "message": "팀장이 탈퇴하여 새 팀장에게 위임되었습니다.",
    }

    with SessionLocal() as db:
        current_team = db.get(Team, team_id)
        assert current_team is not None
        members = db.scalars(
            select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.id.asc())
        ).all()
        roles_by_nickname = {member.user.nickname: member.role for member in members}
        assert roles_by_nickname == {"member3": "leader", "member4": "member"}
        assert current_team.leader.nickname == "member3"

    app.dependency_overrides.clear()


def test_leave_team_leader_last_member_deletes_team_and_children() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader3", "leader3")
        team = _create_team(db, "band-c", leader, [])
        team_id = team.id

        now = datetime.utcnow()
        db.add(TeamNotice(team_id=team.id, title="n1", content="notice"))
        db.add(TeamChecklist(team_id=team.id, content="todo", is_checked=False))
        db.add(
            TeamSchedule(
                team_id=team.id,
                title="practice",
                description="desc",
                start_at=now,
                end_at=now + timedelta(hours=1),
            )
        )
        db.commit()

    resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": "leader3"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "team_deleted": True,
        "message": "팀장이 탈퇴하여 팀이 삭제되었습니다.",
    }

    with SessionLocal() as db:
        assert db.get(Team, team_id) is None
        assert db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)).all() == []
        assert db.scalars(select(TeamNotice).where(TeamNotice.team_id == team_id)).all() == []
        assert db.scalars(select(TeamChecklist).where(TeamChecklist.team_id == team_id)).all() == []
        assert db.scalars(select(TeamSchedule).where(TeamSchedule.team_id == team_id)).all() == []

    app.dependency_overrides.clear()


def test_leave_team_invalid_nickname_and_team_cases() -> None:
    client, SessionLocal = _make_client_and_sessionmaker()

    with SessionLocal() as db:
        leader = _create_user(db, "leader4", "leader4")
        member = _create_user(db, "member5", "member5")
        outsider = _create_user(db, "outsider1", "outsider1")
        team = _create_team(db, "band-d", leader, [member])
        team_id = team.id
        outsider_nickname = outsider.nickname

    not_found_team_resp = client.post("/api/team/99999/leave", json={"nickname": "leader4"})
    assert not_found_team_resp.status_code == 404

    empty_nickname_resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": "  "})
    assert empty_nickname_resp.status_code == 400

    missing_nickname_resp = client.post(f"/api/team/{team_id}/leave", json={})
    assert missing_nickname_resp.status_code == 400

    outsider_resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": outsider_nickname})
    assert outsider_resp.status_code == 403

    unknown_user_resp = client.post(f"/api/team/{team_id}/leave", json={"nickname": "no-such-user"})
    assert unknown_user_resp.status_code == 404

    app.dependency_overrides.clear()
