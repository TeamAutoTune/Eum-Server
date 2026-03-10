from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.board import BoardPerformance, BoardReview, FreeBoardComment, FreeBoardPost
from app.schemas.board import (
    BoardReviewCreateRequest,
    FreeBoardCommentCreateRequest,
    FreeBoardPostCreateRequest,
)


def list_performances(db: Session) -> list[BoardPerformance]:
    return db.scalars(select(BoardPerformance).order_by(BoardPerformance.date.asc())).all()


def get_performance(db: Session, performance_id: int) -> BoardPerformance:
    performance = db.get(BoardPerformance, performance_id)
    if not performance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance not found")
    return performance


def list_reviews(
    db: Session,
    performance_id: int | None = None,
    review_type: str | None = None,
) -> list[BoardReview]:
    query = select(BoardReview).order_by(BoardReview.created_at.desc())
    if performance_id is not None:
        query = query.where(BoardReview.performance_id == performance_id)
    if review_type is not None:
        query = query.where(BoardReview.type == review_type)
    return db.scalars(query).all()


def create_review(db: Session, payload: BoardReviewCreateRequest) -> BoardReview:
    get_performance(db, payload.performance_id)

    review = BoardReview(
        performance_id=payload.performance_id,
        author_name=payload.author_name,
        rating=payload.rating,
        type=payload.type,
        content=payload.content,
        image_url=payload.image_url,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def list_free_posts(db: Session) -> list[FreeBoardPost]:
    query = (
        select(FreeBoardPost)
        .options(selectinload(FreeBoardPost.comments))
        .order_by(FreeBoardPost.created_at.desc())
    )
    return db.scalars(query).all()


def get_free_post(db: Session, post_id: int) -> FreeBoardPost:
    query = (
        select(FreeBoardPost)
        .options(selectinload(FreeBoardPost.comments))
        .where(FreeBoardPost.id == post_id)
    )
    post = db.scalar(query)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def create_free_post(db: Session, payload: FreeBoardPostCreateRequest) -> FreeBoardPost:
    post = FreeBoardPost(author_name=payload.author_name, content=payload.content)
    db.add(post)
    db.commit()
    return get_free_post(db, post.id)


def delete_free_post(db: Session, post_id: int) -> bool:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    db.delete(post)
    db.commit()
    return True


def toggle_free_post_like(db: Session, post_id: int) -> FreeBoardPost:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.liked_by_user:
        post.likes = max(0, post.likes - 1)
        post.liked_by_user = False
    else:
        post.likes += 1
        post.liked_by_user = True

    db.commit()
    db.refresh(post)
    return post


def create_free_post_comment(
    db: Session,
    post_id: int,
    payload: FreeBoardCommentCreateRequest,
) -> FreeBoardComment:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = FreeBoardComment(
        post_id=post_id,
        author_name=payload.author_name,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def seed_board_data(db: Session) -> None:
    has_performance = db.scalar(select(BoardPerformance.id).limit(1))
    if has_performance:
        return

    performances = [
        BoardPerformance(
            title="\ub77c\uc774\ube0c \ub77d \ub098\uc774\ud2b8",
            date="2026-03-15",
            location="\uc62c\ub9bc\ud53d\uacf5\uc6d0",
            genre="\ub77d",
            artist="\uc2e4\ub9ac\uce74\uac94, \uc0c8\uc18c\ub144, \uad6d\uce74\uc2a4\ud150, \uc794\ub098\ube44",
            description="\ubd04 \uc2dc\uc98c \uc624\ud504\ub2dd \uacf5\uc5f0\uc785\ub2c8\ub2e4.",
            image_url="/assets/seoullive.png",
        ),
        BoardPerformance(
            title="\uc7ac\uc988 \ub098\uc774\ud2b8 \ud398\uc2a4\ud2f0\ubc8c",
            date="2026-03-22",
            location="\ubd80\uc0b0 \ubb38\ud654\ud68c\uad00",
            genre="\uc7ac\uc988",
            artist="\ub098\uc724\uc120, Laufey, \ud504\ub810\ub958\ub4dc, \ubb38\ucc28\uc77c\ub4dc",
            description="\ubaa8\ub358 \uc7ac\uc988\uc640 \ud568\uaed8\ud558\ub294 \ub530\ub73b\ud55c \ubc24.",
            image_url="/assets/jazznight.png",
        ),
        BoardPerformance(
            title="\ud074\ub798\uc2dd \ubd04 \ucf58\uc11c\ud2b8",
            date="2026-03-29",
            location="\uc11c\uc6b8 \uc608\uc220\uc758\uc804\ub2f9",
            genre="\ud074\ub798\uc2dd",
            artist="\uc11c\uc6b8 \ud544\ud558\ubaa8\ub2c9",
            description="\uad50\ud5a5\uace1\uacfc \uc2e4\ub0b4\uc545\uc73c\ub85c \uad6c\uc131\ub41c \ud480 \ud504\ub85c\uadf8\ub7a8.",
            image_url="/assets/classicsymphony.png",
        ),
    ]
    db.add_all(performances)
    db.flush()

    db.add_all(
        [
            BoardReview(
                performance_id=performances[0].id,
                author_name="\uc774\uc74c\uc0ac\uc6a9\uc7901",
                rating=5,
                type="found_member",
                content="\ubb34\ub300 \uc5f0\ucd9c\uacfc \uc0ac\uc6b4\ub4dc\uac00 \uc815\ub9d0 \uc88b\uc558\uc5b4\uc694. \ub2e4\uc74c \uacf5\uc5f0\ub3c4 \uae30\ub300\ub429\ub2c8\ub2e4.",
                image_url="/assets/Gemini_Generated_Band.png",
            ),
            BoardReview(
                performance_id=performances[0].id,
                author_name="\uc74c\uc545\uc560\ud638\uac00",
                rating=4,
                type="joined_club",
                content="\ud604\uc7a5 \ubd84\uc704\uae30\uac00 \uc88b\uc558\uace0 \uc14b\ub9ac\uc2a4\ud2b8 \uad6c\uc131\ub3c4 \ub9cc\uc871\uc2a4\ub7ec\uc6e0\uc5b4\uc694.",
            ),
            BoardReview(
                performance_id=performances[1].id,
                author_name="\uc7ac\uc988\ub7ec\ubc84",
                rating=5,
                type="found_member",
                content="\uc7ac\uc988 \uc88b\uc544\ud558\uc2dc\ub294 \ubd84\ub4e4\uaed8 \uaf2d \ucd94\ucc9c\ud558\uace0 \uc2f6\uc740 \uacf5\uc5f0\uc774\uc5c8\uc5b4\uc694.",
            ),
        ]
    )

    posts = [
        FreeBoardPost(author_name="\uc0c8\ubbf8", content="\ubc34\ub4dc \uc5f0\uc2b5 \ub05d\ub0ac\uc5b4\uc694. \ubcf4\uceec \ud55c \ubd84 \ub354 \uad6c\ud569\ub2c8\ub2e4.", likes=24),
        FreeBoardPost(author_name="\ud06c\ub9ac\uc2a4", content="\uc0c1\ud0dc \uc88b\uc740 \uc570\ud504 \ud310\ub9e4\ud569\ub2c8\ub2e4. \uad00\uc2ec \uc788\uc73c\uba74 DM \uc8fc\uc138\uc694.", likes=12),
        FreeBoardPost(author_name="\ubbfc\ud638", content="\ubc34\ub4dc \uc2dc\uc791\ud55c \uc9c0 3\uac1c\uc6d4\uc778\ub370 \uc544\uc9c1\ub3c4 \ub108\ubb34 \uc7ac\ubc0c\uc5b4\uc694.", likes=38),
        FreeBoardPost(author_name="\ubc15\uc9c0\ud6c8", content="\uc774\ubc88 \uc8fc\ub9d0 \uac15\ub0a8 \ucabd \ub77c\uc774\ube0c\ubc14 \ucd94\ucc9c\ud574 \uc8fc\uc138\uc694.", likes=18),
        FreeBoardPost(author_name="\ub77c\uc774\uc5b8", content="\ucd08\ubcf4\uc790\uc6a9 \uae30\ud0c0 \ub808\uc2a8 \ucd94\ucc9c \ubd80\ud0c1\ub4dc\ub824\uc694.", likes=15),
        FreeBoardPost(author_name="JK", content="\ud3c9\uc77c \ubc24\uc5d0 \uac00\ubccd\uac8c \ud569\uc8fc\ud560 \ubaa8\uc784 \ucc3e\uace0 \uc788\uc5b4\uc694.", likes=42),
        FreeBoardPost(author_name="\ubcf4\uc2a4", content="\ud559\uad50 \uadfc\ucc98 \ud569\uc8fc\uc2e4 \uc2dc\uac04 \ub098\ub214 \uac00\ub2a5\ud55c \ubd84 \uc788\ub098\uc694?", likes=28),
        FreeBoardPost(author_name="\ud61c\uc9c4", content="\uccab \ubb34\ub300 \uacf5\uc5f0 \ub05d\ub0c8\uc5b4\uc694. \uc815\ub9d0 \uc88b\uc740 \uacbd\ud5d8\uc774\uc5c8\uc5b4\uc694.", likes=56),
    ]
    db.add_all(posts)
    db.flush()

    db.add_all(
        [
            FreeBoardComment(post_id=posts[0].id, author_name="\uc774\uc11c\uc5f0", content="\ucd95\ud558\ud574\uc694. \uc5b4\ub5a4 \uc7a5\ub974 \ud558\uc2dc\ub098\uc694?"),
            FreeBoardComment(post_id=posts[0].id, author_name="\uae40\ud558\ub298", content="\uc88b\ub124\uc694!"),
            FreeBoardComment(post_id=posts[1].id, author_name="\ubc15\uc9c0\ud6c8", content="\uac00\uaca9\uc740 \uc5bc\ub9c8\uc778\uac00\uc694?"),
        ]
    )
    db.commit()
