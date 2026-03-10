from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.board import DeleteResponse
from app.schemas.team_checklist import TeamChecklistCreateRequest, TeamChecklistResponse, TeamChecklistUpdateRequest
from app.services import team_checklist_service

router = APIRouter()


def _to_response(checklist) -> TeamChecklistResponse:
    return TeamChecklistResponse(
        checklist_id=checklist.id,
        team_id=checklist.team_id,
        content=checklist.content,
        is_checked=checklist.is_checked,
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
    )


@router.get("/{team_id}/checklists", response_model=list[TeamChecklistResponse])
def list_checklists(team_id: int, db: Session = Depends(get_db)):
    checklists = team_checklist_service.list_checklists(db, team_id)
    return [_to_response(checklist) for checklist in checklists]


@router.post("/{team_id}/checklists", response_model=TeamChecklistResponse, status_code=status.HTTP_201_CREATED)
def create_checklist(team_id: int, payload: TeamChecklistCreateRequest, db: Session = Depends(get_db)):
    checklist = team_checklist_service.create_checklist(db, team_id, payload)
    return _to_response(checklist)


@router.patch("/checklists/{checklist_id}", response_model=TeamChecklistResponse)
def update_checklist(checklist_id: int, payload: TeamChecklistUpdateRequest, db: Session = Depends(get_db)):
    checklist = team_checklist_service.update_checklist(db, checklist_id, payload)
    return _to_response(checklist)


@router.delete("/checklists/{checklist_id}", response_model=DeleteResponse)
def delete_checklist(checklist_id: int, db: Session = Depends(get_db)):
    result = team_checklist_service.delete_checklist(db, checklist_id)
    return DeleteResponse(success=result["success"])
