from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team, TeamSchedule
from app.schemas.team_schedule import TeamScheduleCreateRequest, TeamScheduleUpdateRequest


def _get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _get_schedule_or_404(db: Session, schedule_id: int) -> TeamSchedule:
    schedule = db.get(TeamSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule


def _validate_schedule_range(start_at, end_at) -> None:
    if start_at >= end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_at must be earlier than end_at",
        )


def list_schedules(db: Session, team_id: int) -> list[TeamSchedule]:
    _get_team_or_404(db, team_id)
    return db.scalars(
        select(TeamSchedule)
        .where(TeamSchedule.team_id == team_id)
        .order_by(TeamSchedule.start_at.asc())
    ).all()


def create_schedule(db: Session, team_id: int, payload: TeamScheduleCreateRequest) -> TeamSchedule:
    _get_team_or_404(db, team_id)
    _validate_schedule_range(payload.start_at, payload.end_at)
    schedule = TeamSchedule(
        team_id=team_id,
        title=payload.title,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(db: Session, schedule_id: int, payload: TeamScheduleUpdateRequest) -> TeamSchedule:
    schedule = _get_schedule_or_404(db, schedule_id)

    start_at = payload.start_at if payload.start_at is not None else schedule.start_at
    end_at = payload.end_at if payload.end_at is not None else schedule.end_at
    _validate_schedule_range(start_at, end_at)

    if payload.title is not None:
        schedule.title = payload.title
    if payload.description is not None:
        schedule.description = payload.description
    if payload.start_at is not None:
        schedule.start_at = payload.start_at
    if payload.end_at is not None:
        schedule.end_at = payload.end_at

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> dict[str, bool]:
    schedule = _get_schedule_or_404(db, schedule_id)
    db.delete(schedule)
    db.commit()
    return {"success": True}
