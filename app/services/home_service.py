from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.home import Review, TeamPromotion


def list_reviews(db: Session) -> list[Review]:
    return db.scalars(select(Review).order_by(Review.created_at.desc())).all()


def list_promotions(db: Session) -> list[TeamPromotion]:
    return db.scalars(select(TeamPromotion).order_by(TeamPromotion.created_at.desc())).all()


def create_review(db: Session, title: str, body: str) -> Review:
    review = Review(title=title, body=body)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def create_promotion(db: Session, team_name: str, summary: str) -> TeamPromotion:
    promotion = TeamPromotion(team_name=team_name, summary=summary)
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return promotion
