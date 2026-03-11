from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.team import (
    MyTeamItemResponse,
    MyTeamResponse,
    TeamCreateRequest,
    TeamCreateResponse,
    TeamDetailResponse,
    TeamInviteItemResponse,
    TeamInviteListResponse,
    TeamInviteRequest,
    TeamInviteResponse,
    TeamLeaveRequest,
    TeamLeaveResponse,
    TeamListItemResponse,
)
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
            average_age=team.average_age,
            region=team.region,
            genres=team_service.team_genres(team),
            gender_ratio=team.gender_ratio,
            reference_songs=team_service.team_reference_songs(team),
        )
        for team in teams
    ]


@router.get("/my", response_model=MyTeamResponse)
def get_my_team(nickname: str, db: Session = Depends(get_db)):
    team = team_service.get_my_team_by_nickname(db, nickname)
    if not team:
        return MyTeamResponse(has_team=False, team=None)

    return MyTeamResponse(
        has_team=True,
        team=MyTeamItemResponse(
            team_id=team.id,
            team_name=team.team_name,
            description=team.description,
            leader=team.leader.nickname,
            average_age=team.average_age,
            region=team.region,
            genres=team_service.team_genres(team),
            gender_ratio=team.gender_ratio,
            reference_songs=team_service.team_reference_songs(team),
        ),
    )


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
        average_age=team.average_age,
        region=team.region,
        genres=team_service.team_genres(team),
        gender_ratio=team.gender_ratio,
        reference_songs=team_service.team_reference_songs(team),
    )


@router.post("/{team_id}/invite", response_model=TeamInviteResponse)
def invite_team_member(
    team_id: int,
    payload: TeamInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite = team_service.create_team_invite(db, team_id, payload, current_user)
    return TeamInviteResponse(
        ok=True,
        team_id=invite.team_id,
        invited_user_id=invite.invited_user_id,
        invited_nickname=invite.invited_user.nickname,
        status=invite.status,
    )


@router.get("/{team_id}/invites", response_model=TeamInviteListResponse)
def get_team_invites(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invites = team_service.list_team_invites(db, team_id, current_user)
    return TeamInviteListResponse(
        invites=[
            TeamInviteItemResponse(
                invite_id=invite.id,
                team_id=invite.team_id,
                invited_user_id=invite.invited_user_id,
                invited_nickname=invite.invited_user.nickname,
                invited_by_user_id=invite.invited_by_user_id,
                invited_by_nickname=invite.invited_by_user.nickname,
                status=invite.status,
            )
            for invite in invites
        ]
    )


@router.post(
    "/{team_id}/leave",
    response_model=TeamLeaveResponse,
    responses={
        400: {"description": "nickname 없음/빈값"},
        403: {"description": "권한 없는 탈퇴 요청"},
        404: {"description": "team_id 또는 nickname 사용자 없음"},
        500: {"description": "서버 에러"},
    },
)
def leave_team(team_id: int, payload: TeamLeaveRequest, db: Session = Depends(get_db)):
    result = team_service.leave_team(db, team_id, payload.nickname)
    return TeamLeaveResponse(**result)
