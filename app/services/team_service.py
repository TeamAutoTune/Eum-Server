from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamMember
from app.models.user import User
from app.schemas.team import TeamCreateRequest


def _get_user_by_nickname(db: Session, nickname: str) -> User | None:
    return db.scalar(select(User).where(User.nickname == nickname))


def _get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def create_team(db: Session, payload: TeamCreateRequest) -> Team:
    leader = _get_user_by_nickname(db, payload.leader_nickname)
    if not leader:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leader user not found")

    normalized_members: list[str] = []
    seen: set[str] = set()
    for nickname in payload.members:
        cleaned = nickname.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized_members.append(cleaned)

    if payload.leader_nickname.lower() in {name.lower() for name in normalized_members}:
        normalized_members = [name for name in normalized_members if name.lower() != payload.leader_nickname.lower()]

    users = db.scalars(select(User).where(User.nickname.in_(normalized_members))).all() if normalized_members else []
    user_by_nickname = {user.nickname: user for user in users}

    missing = [nickname for nickname in normalized_members if nickname not in user_by_nickname]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member user not found: {', '.join(missing)}",
        )

    team = Team(
        team_name=payload.team_name,
        description=payload.description,
        leader_id=leader.id,
    )
    db.add(team)
    db.flush()

    db.add(TeamMember(team_id=team.id, user_id=leader.id, role="leader"))
    for nickname in normalized_members:
        member_user = user_by_nickname[nickname]
        db.add(TeamMember(team_id=team.id, user_id=member_user.id, role="member"))

    db.commit()
    db.refresh(team)
    return team


def list_teams(db: Session) -> list[Team]:
    return db.scalars(select(Team).order_by(Team.created_at.desc())).all()


def get_team_detail(db: Session, team_id: int) -> Team:
    return _get_team_or_404(db, team_id)


def get_my_team_by_nickname(db: Session, nickname: str) -> Team | None:
    user = _get_user_by_nickname(db, nickname)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {nickname}",
        )

    team = db.scalar(
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id)
        .order_by(Team.created_at.desc())
    )
    if team:
        return team

    return db.scalar(
        select(Team)
        .where(Team.leader_id == user.id)
        .order_by(Team.created_at.desc())
    )


def list_team_member_nicknames(db: Session, team_id: int, include_leader: bool = False) -> list[str]:
    _get_team_or_404(db, team_id)
    members = db.scalars(
        select(TeamMember)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.id.asc())
    ).all()
    if not members:
        return []

    users = db.scalars(select(User).where(User.id.in_([member.user_id for member in members]))).all()
    nickname_map = {user.id: user.nickname for user in users}

    nicknames: list[str] = []
    for member in members:
        if not include_leader and member.role == "leader":
            continue
        nickname = nickname_map.get(member.user_id)
        if nickname:
            nicknames.append(nickname)
    return nicknames
