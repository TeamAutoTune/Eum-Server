from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamChecklist
from app.schemas.team_checklist import TeamChecklistCreateRequest, TeamChecklistUpdateRequest


def _get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _get_checklist_or_404(db: Session, checklist_id: int) -> TeamChecklist:
    checklist = db.get(TeamChecklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    return checklist


def list_checklists(db: Session, team_id: int) -> list[TeamChecklist]:
    _get_team_or_404(db, team_id)
    return db.scalars(
        select(TeamChecklist)
        .where(TeamChecklist.team_id == team_id)
        .order_by(TeamChecklist.created_at.asc())
    ).all()


def create_checklist(db: Session, team_id: int, payload: TeamChecklistCreateRequest) -> TeamChecklist:
    _get_team_or_404(db, team_id)
    checklist = TeamChecklist(team_id=team_id, content=payload.content, is_checked=False)
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return checklist


def update_checklist(db: Session, checklist_id: int, payload: TeamChecklistUpdateRequest) -> TeamChecklist:
    checklist = _get_checklist_or_404(db, checklist_id)
    if payload.content is not None:
        checklist.content = payload.content
    if payload.is_checked is not None:
        checklist.is_checked = payload.is_checked
    db.commit()
    db.refresh(checklist)
    return checklist


def delete_checklist(db: Session, checklist_id: int) -> dict[str, bool]:
    checklist = _get_checklist_or_404(db, checklist_id)
    db.delete(checklist)
    db.commit()
    return {"success": True}
