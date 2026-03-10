from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.board import (
    BoardPerformanceOut,
    BoardReviewCreateRequest,
    BoardReviewOut,
    DeleteResponse,
    FreeBoardCommentCreateRequest,
    FreeBoardCommentOut,
    FreeBoardLikeToggleResponse,
    FreeBoardPostCreateRequest,
    FreeBoardPostOut,
)
from app.services import board_service

router = APIRouter()


def post_to_schema(post) -> FreeBoardPostOut:
    return FreeBoardPostOut(
        id=post.id,
        author_name=post.author_name,
        content=post.content,
        likes=post.likes,
        liked_by_user=post.liked_by_user,
        comments_count=len(post.comments),
        comments_list=post.comments,
        created_at=post.created_at,
    )


@router.get("/performances", response_model=list[BoardPerformanceOut])
def list_performances(db: Session = Depends(get_db)):
    return board_service.list_performances(db)


@router.get("/performances/{performance_id}", response_model=BoardPerformanceOut)
def get_performance(performance_id: int, db: Session = Depends(get_db)):
    return board_service.get_performance(db, performance_id)


@router.get("/reviews", response_model=list[BoardReviewOut])
def list_reviews(
    performance_id: int | None = Query(default=None),
    review_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return board_service.list_reviews(db, performance_id, review_type)


@router.post("/reviews", response_model=BoardReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(payload: BoardReviewCreateRequest, db: Session = Depends(get_db)):
    return board_service.create_review(db, payload)


@router.get("/free-posts", response_model=list[FreeBoardPostOut])
def list_free_posts(db: Session = Depends(get_db)):
    posts = board_service.list_free_posts(db)
    return [post_to_schema(post) for post in posts]


@router.post("/free-posts", response_model=FreeBoardPostOut, status_code=status.HTTP_201_CREATED)
def create_free_post(payload: FreeBoardPostCreateRequest, db: Session = Depends(get_db)):
    post = board_service.create_free_post(db, payload)
    return post_to_schema(post)


@router.delete("/free-posts/{post_id}", response_model=DeleteResponse)
def delete_free_post(post_id: int, db: Session = Depends(get_db)):
    success = board_service.delete_free_post(db, post_id)
    return DeleteResponse(success=success)


@router.post("/free-posts/{post_id}/likes", response_model=FreeBoardLikeToggleResponse)
def toggle_free_post_like(post_id: int, db: Session = Depends(get_db)):
    post = board_service.toggle_free_post_like(db, post_id)
    return FreeBoardLikeToggleResponse(
        post_id=post.id,
        likes=post.likes,
        liked_by_user=post.liked_by_user,
    )


@router.post("/free-posts/{post_id}/comments", response_model=FreeBoardCommentOut, status_code=status.HTTP_201_CREATED)
def create_free_post_comment(
    post_id: int,
    payload: FreeBoardCommentCreateRequest,
    db: Session = Depends(get_db),
):
    return board_service.create_free_post_comment(db, post_id, payload)
