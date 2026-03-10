from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.matching import (
    MatchingEventRequest,
    MatchingRecommendRequest,
    MatchingRecommendResponse,
)
from app.services.matching_service import record_match_event, recommend_matches

router = APIRouter()


@router.post("/match", response_model=MatchingRecommendResponse)
def match(
    payload: MatchingRecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recommend_matches(
        db=db,
        profile=payload.profile,
        mode=payload.mode,
        min_score=payload.min_score,
        limit=payload.limit,
        recruit_needs=payload.recruit_needs,
        hard_filters=payload.hard_filters,
        viewer_id=current_user.id,
        ranking_version=payload.ranking_version,
    )


@router.post("/recommend", response_model=MatchingRecommendResponse)
def recommend(
    payload: MatchingRecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return match(payload=payload, db=db, current_user=current_user)


@router.post("/match-event")
def match_event(
    payload: MatchingEventRequest,
    current_user: User = Depends(get_current_user),
):
    return record_match_event(
        viewer_id=current_user.id,
        candidate_id=payload.candidate_id,
        recommendation_id=payload.recommendation_id,
        event_type=payload.event_type,
        mode=payload.mode,
        match_score=payload.matchScore,
        rank_position=payload.rank_position,
        extra=payload.extra,
    )
