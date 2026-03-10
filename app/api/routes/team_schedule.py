from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.board import DeleteResponse
from app.schemas.team_schedule import TeamScheduleCreateRequest, TeamScheduleResponse, TeamScheduleUpdateRequest
from app.services import team_schedule_service

router = APIRouter()


def _to_response(schedule) -> TeamScheduleResponse:
    return TeamScheduleResponse(
        schedule_id=schedule.id,
        team_id=schedule.team_id,
        title=schedule.title,
        description=schedule.description,
        start_at=schedule.start_at,
        end_at=schedule.end_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


@router.get("/{team_id}/schedules", response_model=list[TeamScheduleResponse])
def list_schedules(team_id: int, db: Session = Depends(get_db)):
    schedules = team_schedule_service.list_schedules(db, team_id)
    return [_to_response(schedule) for schedule in schedules]


@router.post("/{team_id}/schedules", response_model=TeamScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(team_id: int, payload: TeamScheduleCreateRequest, db: Session = Depends(get_db)):
    schedule = team_schedule_service.create_schedule(db, team_id, payload)
    return _to_response(schedule)


@router.patch("/schedules/{schedule_id}", response_model=TeamScheduleResponse)
def update_schedule(schedule_id: int, payload: TeamScheduleUpdateRequest, db: Session = Depends(get_db)):
    schedule = team_schedule_service.update_schedule(db, schedule_id, payload)
    return _to_response(schedule)


@router.delete("/schedules/{schedule_id}", response_model=DeleteResponse)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    result = team_schedule_service.delete_schedule(db, schedule_id)
    return DeleteResponse(success=result["success"])
