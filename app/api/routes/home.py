from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.home import (
    ReviewCreateRequest,
    ReviewOut,
    TeamPromotionCreateRequest,
    TeamPromotionOut,
)
from app.services import home_service

router = APIRouter()


@router.get("/reviews", response_model=list[ReviewOut])
def reviews(db: Session = Depends(get_db)):
    return home_service.list_reviews(db)


@router.get("/promotions", response_model=list[TeamPromotionOut])
def promotions(db: Session = Depends(get_db)):
    return home_service.list_promotions(db)


@router.post("/reviews", response_model=ReviewOut)
def create_review(payload: ReviewCreateRequest, db: Session = Depends(get_db)):
    return home_service.create_review(db, payload.title, payload.body)


@router.post("/promotions", response_model=TeamPromotionOut)
def create_promotion(payload: TeamPromotionCreateRequest, db: Session = Depends(get_db)):
    return home_service.create_promotion(db, payload.team_name, payload.summary)
