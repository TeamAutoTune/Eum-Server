from fastapi import HTTPException, status
from sqlalchemy import and_, func, literal, select
from sqlalchemy.orm import Session, selectinload

from app.models.board import (
    BoardPerformance,
    BoardReview,
    FreeBoardComment,
    FreeBoardPost,
    FreeBoardPostLike,
)
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
        image_urls=payload.image_urls,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def _likes_expr():
    return (
        select(FreeBoardPostLike.post_id, func.count().label("likes"))
        .group_by(FreeBoardPostLike.post_id)
        .subquery()
    )


def _liked_by_user_expr(current_user_id: str | None):
    if not current_user_id:
        return literal(False)
    return (
        select(func.count())
        .where(
            and_(
                FreeBoardPostLike.post_id == FreeBoardPost.id,
                FreeBoardPostLike.user_id == current_user_id,
            )
        )
        .correlate(FreeBoardPost)
        .scalar_subquery()
        > 0
    )


def list_free_posts(db: Session, current_user_id: str | None) -> list[dict]:
    likes_subq = _likes_expr()
    liked_expr = _liked_by_user_expr(current_user_id)

    query = (
        select(
            FreeBoardPost,
            func.coalesce(likes_subq.c.likes, 0).label("likes"),
            liked_expr.label("liked_by_user"),
        )
        .options(selectinload(FreeBoardPost.comments))
        .outerjoin(likes_subq, FreeBoardPost.id == likes_subq.c.post_id)
        .order_by(FreeBoardPost.created_at.desc())
    )
    rows = db.execute(query).all()
    return [
        {
            "post": row[0],
            "likes": int(row[1] or 0),
            "liked_by_user": bool(row[2]),
        }
        for row in rows
    ]


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


def get_free_post_with_meta(db: Session, post_id: int, current_user_id: str | None) -> dict:
    likes_subq = _likes_expr()
    liked_expr = _liked_by_user_expr(current_user_id)

    query = (
        select(
            FreeBoardPost,
            func.coalesce(likes_subq.c.likes, 0).label("likes"),
            liked_expr.label("liked_by_user"),
        )
        .options(selectinload(FreeBoardPost.comments))
        .outerjoin(likes_subq, FreeBoardPost.id == likes_subq.c.post_id)
        .where(FreeBoardPost.id == post_id)
    )
    row = db.execute(query).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return {"post": row[0], "likes": int(row[1] or 0), "liked_by_user": bool(row[2])}


def create_free_post(db: Session, payload: FreeBoardPostCreateRequest, current_user_id: str | None) -> dict:
    post = FreeBoardPost(author_name=payload.author_name, content=payload.content)
    db.add(post)
    db.commit()
    return get_free_post_with_meta(db, post.id, current_user_id)


def delete_free_post(db: Session, post_id: int) -> bool:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    db.delete(post)
    db.commit()
    return True


def toggle_free_post_like(db: Session, post_id: int, user_id: str) -> dict:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    existing = db.scalar(
        select(FreeBoardPostLike).where(
            and_(FreeBoardPostLike.post_id == post_id, FreeBoardPostLike.user_id == user_id)
        )
    )
    if existing:
        db.delete(existing)
    else:
        db.add(FreeBoardPostLike(post_id=post_id, user_id=user_id))

    db.commit()
    return get_free_post_with_meta(db, post_id, user_id)


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
            title="라이브 락 나이트",
            date="2026-03-15",
            location="올림픽공원",
            genre="락",
            artist="실리카겔, 새소년, 국카스텐, 잔나비",
            description="봄 시즌 오프닝 공연입니다.",
            image_url="/assets/seoullive.png",
        ),
        BoardPerformance(
            title="재즈 나이트 페스티벌",
            date="2026-03-22",
            location="부산 문화회관",
            genre="재즈",
            artist="나윤선, Laufey, 프렐류드, 문차일드",
            description="모던 재즈와 함께하는 따뜻한 밤.",
            image_url="/assets/jazznight.png",
        ),
        BoardPerformance(
            title="클래식 봄 콘서트",
            date="2026-03-29",
            location="서울 예술의전당",
            genre="클래식",
            artist="서울 필하모닉",
            description="교향곡과 실내악으로 구성된 풀 프로그램.",
            image_url="/assets/classicsymphony.png",
        ),
    ]
    db.add_all(performances)
    db.flush()

    db.add_all(
        [
            BoardReview(
                performance_id=performances[0].id,
                author_name="이음사용자1",
                rating=5,
                type="found_member",
                content="무대 연출과 사운드가 정말 좋았어요. 다음 공연도 기대됩니다.",
                image_urls=["/assets/Gemini_Generated_Band.png"],
            ),
            BoardReview(
                performance_id=performances[0].id,
                author_name="음악애호가",
                rating=4,
                type="joined_club",
                content="현장 분위기가 좋았고 셋리스트 구성도 만족스러웠어요.",
            ),
            BoardReview(
                performance_id=performances[1].id,
                author_name="재즈러버",
                rating=5,
                type="found_member",
                content="재즈 좋아하시는 분들께 꼭 추천하고 싶은 공연이었어요.",
            ),
        ]
    )

    posts = [
        FreeBoardPost(author_name="새미", content="밴드 연습 끝났어요. 보컬 한 분 더 구합니다."),
        FreeBoardPost(author_name="크리스", content="상태 좋은 앰프 판매합니다. 관심 있으면 DM 주세요."),
        FreeBoardPost(author_name="민호", content="밴드 시작한 지 3개월인데 아직도 너무 재밌어요."),
        FreeBoardPost(author_name="박지훈", content="이번 주말 강남 쪽 라이브바 추천해 주세요."),
        FreeBoardPost(author_name="라이언", content="초보자용 기타 레슨 추천 부탁드려요."),
        FreeBoardPost(author_name="JK", content="평일 밤에 가볍게 합주할 모임 찾고 있어요."),
        FreeBoardPost(author_name="보스", content="학교 근처 합주실 시간 나눔 가능한 분 있나요?"),
        FreeBoardPost(author_name="혜진", content="첫 무대 공연 끝냈어요. 정말 좋은 경험이었어요."),
    ]
    db.add_all(posts)
    db.flush()

    db.add_all(
        [
            FreeBoardComment(post_id=posts[0].id, author_name="이서연", content="축하해요. 어떤 장르 하시나요?"),
            FreeBoardComment(post_id=posts[0].id, author_name="김하늘", content="좋네요!"),
            FreeBoardComment(post_id=posts[1].id, author_name="박지훈", content="가격은 얼마인가요?"),
        ]
    )
    db.commit()
