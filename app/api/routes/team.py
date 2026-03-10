from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.team import TeamCreateRequest, TeamCreateResponse, TeamDetailResponse, TeamListItemResponse
from app.services import team_service

router = APIRouter()


@router.post("/create", response_model=TeamCreateResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreateRequest, db: Session = Depends(get_db)):
    team = team_service.create_team(db, payload)
    members = team_service.list_team_member_nicknames(db, team.id, include_leader=False)
    return TeamCreateResponse(
        team_id=team.id,
        team_name=team.team_name,
        leader=team.leader.nickname,
        members=members,
    )


@router.get("/list", response_model=list[TeamListItemResponse])
def list_teams(db: Session = Depends(get_db)):
    teams = team_service.list_teams(db)
    return [
        TeamListItemResponse(
            team_id=team.id,
            team_name=team.team_name,
            description=team.description,
            leader=team.leader.nickname,
        )
        for team in teams
    ]


@router.get("/{team_id}", response_model=TeamDetailResponse)
def get_team_detail(team_id: int, db: Session = Depends(get_db)):
    team = team_service.get_team_detail(db, team_id)
    members = team_service.list_team_member_nicknames(db, team_id, include_leader=False)
    return TeamDetailResponse(
        team_id=team.id,
        team_name=team.team_name,
        description=team.description,
        leader=team.leader.nickname,
        members=members,
    )
