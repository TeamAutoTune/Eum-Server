from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.board import DeleteResponse
from app.schemas.team_notice import TeamNoticeCreateRequest, TeamNoticeResponse, TeamNoticeUpdateRequest
from app.services import team_notice_service

router = APIRouter()


def _to_response(notice) -> TeamNoticeResponse:
    return TeamNoticeResponse(
        notice_id=notice.id,
        team_id=notice.team_id,
        title=notice.title,
        content=notice.content,
        created_at=notice.created_at,
        updated_at=notice.updated_at,
    )


@router.get("/{team_id}/notices", response_model=list[TeamNoticeResponse])
def list_notices(team_id: int, db: Session = Depends(get_db)):
    notices = team_notice_service.list_notices(db, team_id)
    return [_to_response(notice) for notice in notices]


@router.post("/{team_id}/notices", response_model=TeamNoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice(team_id: int, payload: TeamNoticeCreateRequest, db: Session = Depends(get_db)):
    notice = team_notice_service.create_notice(db, team_id, payload)
    return _to_response(notice)


@router.patch("/notices/{notice_id}", response_model=TeamNoticeResponse)
def update_notice(notice_id: int, payload: TeamNoticeUpdateRequest, db: Session = Depends(get_db)):
    notice = team_notice_service.update_notice(db, notice_id, payload)
    return _to_response(notice)


@router.delete("/notices/{notice_id}", response_model=DeleteResponse)
def delete_notice(notice_id: int, db: Session = Depends(get_db)):
    result = team_notice_service.delete_notice(db, notice_id)
    return DeleteResponse(success=result["success"])
