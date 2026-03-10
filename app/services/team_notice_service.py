from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamNotice
from app.schemas.team_notice import TeamNoticeCreateRequest, TeamNoticeUpdateRequest


def _get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _get_notice_or_404(db: Session, notice_id: int) -> TeamNotice:
    notice = db.get(TeamNotice, notice_id)
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return notice


def list_notices(db: Session, team_id: int) -> list[TeamNotice]:
    _get_team_or_404(db, team_id)
    return db.scalars(
        select(TeamNotice)
        .where(TeamNotice.team_id == team_id)
        .order_by(TeamNotice.created_at.desc())
    ).all()


def create_notice(db: Session, team_id: int, payload: TeamNoticeCreateRequest) -> TeamNotice:
    _get_team_or_404(db, team_id)
    notice = TeamNotice(team_id=team_id, title=payload.title, content=payload.content)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


def update_notice(db: Session, notice_id: int, payload: TeamNoticeUpdateRequest) -> TeamNotice:
    notice = _get_notice_or_404(db, notice_id)
    if payload.title is not None:
        notice.title = payload.title
    if payload.content is not None:
        notice.content = payload.content
    db.commit()
    db.refresh(notice)
    return notice


def delete_notice(db: Session, notice_id: int) -> dict[str, bool]:
    notice = _get_notice_or_404(db, notice_id)
    db.delete(notice)
    db.commit()
    return {"success": True}
