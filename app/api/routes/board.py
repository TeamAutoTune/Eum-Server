import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.models.user import User
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
upload_router = APIRouter()


def _post_to_schema(meta: dict) -> FreeBoardPostOut:
    post = meta["post"]
    return FreeBoardPostOut(
        id=post.id,
        author_name=post.author_name,
        content=post.content,
        likes=meta["likes"],
        liked_by_user=meta["liked_by_user"],
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
def create_review(
    payload: BoardReviewCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return board_service.create_review(db, payload)


@router.get("/free-posts", response_model=list[FreeBoardPostOut])
def list_free_posts(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    posts = board_service.list_free_posts(db, current_user.id if current_user else None)
    return [_post_to_schema(meta) for meta in posts]


@router.post("/free-posts", response_model=FreeBoardPostOut, status_code=status.HTTP_201_CREATED)
def create_free_post(
    payload: FreeBoardPostCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meta = board_service.create_free_post(db, payload, current_user.id)
    return _post_to_schema(meta)


@router.delete("/free-posts/{post_id}", response_model=DeleteResponse)
def delete_free_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = board_service.delete_free_post(db, post_id)
    return DeleteResponse(success=success)


@router.post("/free-posts/{post_id}/likes", response_model=FreeBoardLikeToggleResponse)
def toggle_free_post_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meta = board_service.toggle_free_post_like(db, post_id, current_user.id)
    return FreeBoardLikeToggleResponse(
        post_id=post_id,
        likes=meta["likes"],
        liked_by_user=meta["liked_by_user"],
    )


@router.post("/free-posts/{post_id}/comments", response_model=FreeBoardCommentOut, status_code=status.HTTP_201_CREATED)
def create_free_post_comment(
    post_id: int,
    payload: FreeBoardCommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return board_service.create_free_post_comment(db, post_id, payload)


MAX_FILES = 3
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per file
UPLOAD_DIR = Path("static/uploads")


@upload_router.post("/uploads")
async def upload_files(
    request: Request,
    files: Annotated[list[UploadFile], File(..., description="Up to 3 files")],
    current_user: User = Depends(get_current_user),
):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILES * MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="업로드 최대 용량(총 15MB)을 초과했습니다.",
        )

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"최대 {MAX_FILES}개까지 업로드 가능합니다.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []

    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="파일당 최대 5MB까지 업로드 가능합니다.")

        safe_name = Path(file.filename or "upload").name
        filename = f"{uuid.uuid4()}_{safe_name}"
        dest = UPLOAD_DIR / filename
        dest.write_bytes(content)

        url = request.url_for("static", path=f"uploads/{filename}")
        urls.append(str(url))

    return {"urls": urls}
