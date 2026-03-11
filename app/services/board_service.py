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


def delete_performance(db: Session, performance_id: int) -> bool:
    performance = db.get(BoardPerformance, performance_id)
    if not performance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance not found")

    db.delete(performance)
    db.commit()
    return True


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


def delete_review(db: Session, review_id: int) -> bool:
    review = db.get(BoardReview, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    db.delete(review)
    db.commit()
    return True


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
            title="퇴근 후 락 스피릿: 제1회 오피스 락 페스티벌",
            date="2026-03-28",
            location="서울 강남구 역삼동 라이브클럽 '해방",
            genre="Rock",
            artist="부장님 몰래",
            description="서류 가방 대신 기타를 든 직장인들의 반란! 낮에는 평범한 회사원이지만 밤에는 락스타로 변신하는 저희의 열정적인 무대에 여러분을 초대합니다.",
            image_url="/static/uploads/1.png",
        ),
        BoardPerformance(
            title="판교 테크노밸리: 코딩하는 어쿠스틱 밤",
            date="2026-04-04",
            location="경기 성남시 판교 야외 공연장",
            genre="Acoustic",
            artist="개발자 듀오: 디버그(Debug)",
            description="지친 코딩 끝에 찾아온 감성적인 선율. 판교 IT 직장인들이 모여 만든 어쿠스틱 앙상블의 정기 연주회입니다. 퇴근길 가벼운 마음으로 들러주세요.",
            image_url="/static/uploads/2.png",
        ),
        BoardPerformance(
            title="여의도 빌딩 숲 재즈 나잇",
            date="2026-04-11",
            location="서울 영등포구 여의도 펍 '스톡 마켓'",
            genre="Jazz",
            artist="금융인 재즈 퀸텟",
            description="숫자와 차트에서 벗어나 즐기는 세련된 재즈의 밤. 여의도 금융가에서 활동하는 멤버들이 모여 고품격 재즈 스탠다드 넘버를 연주합니다.",
            image_url="/static/uploads/3.png",
        ),
    ]
    db.add_all(performances)
    db.flush()

    db.add_all(
        [
            BoardReview(
                performance_id=performances[0].id,
                author_name="퇴근후기타",
                rating=5,
                type="found_member",
                content="AI 매칭 덕분에 저희 밴드와 성향이 100% 일치하는 드럼 멤버를 구했어요! 퇴근 시간대랑 선호하는 합주 강도까지 비슷해서 일정 잡기가 너무 편합니다. 덕분에 첫 공연도 성공적이었어요!",
                image_urls=["/static/uploads/Gemini_Generated_Band.png"],
            ),
            BoardReview(
                performance_id=performances[0].id,
                author_name="판교베이스",
                rating=5,
                type="joined_club",
                content="평소 좋아하는 장르뿐만 아니라 '취미 위주'라는 활동 목표까지 분석해서 매칭해주니 첫 만남부터 위화감이 없었네요. 덕분에 '디버그' 팀에 합류해서 즐겁게 합주하고 있습니다!",
            ),
            BoardReview(
                performance_id=performances[1].id,
                author_name="여의도색소폰",
                rating=4,
                type="found_member",
                content="직장 생활 패턴에 맞춰 주말 오전 합주가 가능한 분들을 딱딱 매칭해줘서 신기했습니다. AI가 골라준 멤버들과 호흡이 너무 잘 맞아서 이번 재즈 나잇 공연도 무사히 마쳤네요.",
            ),
            BoardReview(
                performance_id=performances[1].id,
                author_name="열혈보컬",
                rating=5,
                type="joined_club",
                content="저는 좀 빡세게 연습하는 스타일인데, AI가 딱 그런 열정적인 팀을 찾아줬어요! 제 음악 취향과 완벽히 일치하는 팀원들을 만나서 요즘 매일이 즐겁습니다.",
            ),
            BoardReview(
                performance_id=performances[2].id,
                author_name="역삼동기타맨",
                rating=5,
                type="found_member",
                content="강남역 근처 주말 오전 합주 가능한 건반 세션을 찾고 있었는데, AI가 딱 맞는 분을 연결해줬어요. 실력뿐만 아니라 성격까지 좋으셔서 이번 정기 공연 준비가 훨씬 수월해졌습니다!",
            ),
            BoardReview(
                performance_id=performances[2].id,
                author_name="메탈스피릿",
                rating=5,
                type="joined_club",
                content="헤비메탈을 좋아해서 팀 찾기가 힘들었는데, AI가 제 취향과 100% 일치하는 팀을 추천해줬어요. 실력파 멤버들과 함께하게 되어 영광입니다. 매칭 알고리즘이 정말 정교하네요!",
                image_urls=["/static/uploads/Gemini_Generated_Image_2.png"],
            ),
            BoardReview(
                performance_id=performances[3].id,
                author_name="어쿠스틱러버",
                rating=4,
                type="found_member",
                content="어쿠스틱 듀오를 결성하고 싶어 보컬분을 찾았는데, 목소리 톤뿐만 아니라 추구하는 음악적 방향까지 비슷한 분을 만나게 되었네요. 덕분에 매주 버스킹 준비하는 재미에 푹 빠졌습니다.",
            ),
            BoardReview(
                performance_id=performances[3].id,
                author_name="퇴근길섹소폰",
                rating=5,
                type="joined_club",
                content="여의도 퇴근길에 가볍게 즐길 수 있는 재즈 팀을 원했는데, AI 매칭 결과가 너무 정확해서 놀랐어요. 스케줄 조율 스트레스 없이 매주 화요일 밤이 기다려집니다.",
            ),
            BoardReview(
                performance_id=performances[4].id,
                author_name="레트로베이시스트",
                rating=5,
                type="found_member",
                content="90년대 가요를 좋아하는 베이시스트를 찾기 힘들었는데, AI 덕분에 추억의 명곡들을 함께 연주할 소중한 멤버를 만났습니다. 취향 기반 매칭의 힘을 실감했어요!",
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
