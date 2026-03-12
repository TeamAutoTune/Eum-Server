from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.onboarding import (
    OnboardingUpsertResponse,
    PersonalOnboardingUpsertRequest,
    TeamOnboardingUpsertRequest,
)
from app.services import onboarding_service

router = APIRouter()


@router.post("/personal", response_model=OnboardingUpsertResponse, status_code=status.HTTP_200_OK)
def upsert_personal_onboarding(
    payload: PersonalOnboardingUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = onboarding_service.upsert_personal_onboarding(db, current_user, payload)
    return OnboardingUpsertResponse(
        profile_id=profile.id,
        summary={
            "user_id": current_user.id,
            "instruments": profile.candidate_data.get("instruments", []),
            "genres": profile.candidate_data.get("genres", []),
            "region": profile.candidate_data.get("region", ""),
        },
    )


@router.post("/team/{team_id}", response_model=OnboardingUpsertResponse, status_code=status.HTTP_200_OK)
def upsert_team_onboarding(
    team_id: int,
    payload: TeamOnboardingUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = onboarding_service.upsert_team_onboarding(
        db,
        team_id=team_id,
        current_user=current_user,
        payload=payload,
    )
    return OnboardingUpsertResponse(
        profile_id=profile.id,
        summary={
            "team_id": team_id,
            "genres": profile.profile_data.get("genres", []),
            "recruit_needs": profile.recruit_needs,
            "region": profile.profile_data.get("region", ""),
        },
    )
