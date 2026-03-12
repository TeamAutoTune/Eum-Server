import json
import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamInvite, TeamMember
from app.models.user import User
from app.schemas.team import TeamCreateRequest, TeamInviteRequest


def _get_user_by_nickname(db: Session, nickname: str) -> User | None:
    return db.scalar(select(User).where(User.nickname == nickname))


def _get_user_by_normalized_nickname(db: Session, nickname: str) -> User | None:
    cleaned = nickname.strip()
    if not cleaned:
        return None
    return db.scalar(select(User).where(func.lower(User.nickname) == cleaned.lower()))


def _clean_text(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_test_account(user: User) -> bool:
    user_id = _clean_text(user.user_id)
    nickname = _clean_text(user.nickname)
    if user_id.startswith("seed_test_") or nickname.startswith("seed_test_"):
        return True
    return bool(re.match(r"^t\d{8}[_-]", user_id) or re.match(r"^t\d{8}[_-]", nickname))


def _normalize_string_list(values: list[str] | None, max_items: int | None = None) -> list[str]:
    if not values:
        return []

    normalized: list[str] = []
    for value in values:
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            continue
        normalized.append(cleaned)

    if max_items is not None:
        normalized = normalized[:max_items]
    return normalized


def _dump_string_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _load_string_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _get_team_member(db: Session, team_id: int, user_id: str) -> TeamMember | None:
    return db.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id))


def _get_user_team_membership(db: Session, user_id: str) -> TeamMember | None:
    return db.scalar(select(TeamMember).where(TeamMember.user_id == user_id).order_by(TeamMember.id.asc()))


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
        description=_clean_text(payload.description),
        average_age=_clean_text(payload.average_age),
        region=_clean_text(payload.region),
        genres=_dump_string_list(_normalize_string_list(payload.genres)),
        gender_ratio=_clean_text(payload.gender_ratio),
        reference_songs=_dump_string_list(_normalize_string_list(payload.reference_songs, max_items=5)),
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


def leave_team(db: Session, team_id: int, nickname: str | None) -> dict[str, bool | str]:
    cleaned_nickname = (nickname or "").strip()
    if not cleaned_nickname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="nickname은 필수입니다.")

    team = _get_team_or_404(db, team_id)
    user = _get_user_by_nickname(db, cleaned_nickname)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    member = db.scalar(
        select(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
        .order_by(TeamMember.id.asc())
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 팀의 멤버가 아닙니다.")

    if member.role != "leader":
        db.delete(member)
        db.commit()
        return {"ok": True, "team_deleted": False, "message": "팀에서 탈퇴했습니다."}

    remaining_members = db.scalars(
        select(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.user_id != user.id)
        .order_by(TeamMember.id.asc())
    ).all()

    if not remaining_members:
        db.delete(team)
        db.commit()
        return {"ok": True, "team_deleted": True, "message": "팀장이 탈퇴하여 팀이 삭제되었습니다."}

    new_leader_member = remaining_members[0]
    new_leader_member.role = "leader"
    team.leader_id = new_leader_member.user_id
    db.delete(member)
    db.commit()
    return {"ok": True, "team_deleted": False, "message": "팀장이 탈퇴하여 새 팀장에게 위임되었습니다."}


def team_genres(team: Team) -> list[str]:
    return _load_string_list(team.genres)


def team_reference_songs(team: Team) -> list[str]:
    return _load_string_list(team.reference_songs)


def create_team_invite(db: Session, team_id: int, payload: TeamInviteRequest, inviter: User) -> TeamInvite:
    _get_team_or_404(db, team_id)

    inviter_membership = _get_team_member(db, team_id, inviter.id)
    if not inviter_membership or inviter_membership.role != "leader":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team leaders can invite users")

    normalized_user_id = _clean_text(payload.user_id)
    normalized_nickname = _clean_text(payload.nickname)

    target_user: User | None = None
    if normalized_user_id:
        target_user = db.scalar(select(User).where(User.id == normalized_user_id))
        if not target_user:
            target_user = db.scalar(select(User).where(User.user_id == normalized_user_id))
    elif normalized_nickname:
        target_user = _get_user_by_normalized_nickname(db, normalized_nickname)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="nickname or user_id is required",
        )

    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    if target_user.id == inviter.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot invite yourself")

    existing_member = _get_team_member(db, team_id, target_user.id)
    if existing_member:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a team member")

    existing_membership = _get_user_team_membership(db, target_user.id)
    if existing_membership and existing_membership.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to another team")

    existing_invite = db.scalar(
        select(TeamInvite).where(
            TeamInvite.team_id == team_id,
            TeamInvite.invited_user_id == target_user.id,
            TeamInvite.status == "invited",
        )
    )
    if existing_invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already invited")

    invite_status = "joined" if payload.auto_accept_test and _is_test_account(target_user) else "invited"

    invite = TeamInvite(
        team_id=team_id,
        invited_user_id=target_user.id,
        invited_by_user_id=inviter.id,
        status=invite_status,
    )
    db.add(invite)
    if invite_status == "joined":
        db.add(TeamMember(team_id=team_id, user_id=target_user.id, role="member"))
    db.commit()
    db.refresh(invite)
    return invite


def list_team_invites(db: Session, team_id: int, current_user: User) -> list[TeamInvite]:
    _get_team_or_404(db, team_id)

    membership = _get_team_member(db, team_id, current_user.id)
    if not membership or membership.role != "leader":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team leaders can view invites")

    return db.scalars(
        select(TeamInvite)
        .where(TeamInvite.team_id == team_id, TeamInvite.status == "invited")
        .order_by(TeamInvite.created_at.desc())
    ).all()
