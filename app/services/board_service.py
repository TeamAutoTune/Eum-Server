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

# --- 기본 CRUD 함수들 ---

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

def list_reviews(db: Session, performance_id: int | None = None, review_type: str | None = None) -> list[BoardReview]:
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

# --- 자유게시판 및 좋아요 관련 (표현식) ---

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
        .where(and_(FreeBoardPostLike.post_id == FreeBoardPost.id, FreeBoardPostLike.user_id == current_user_id))
        .correlate(FreeBoardPost)
        .scalar_subquery()
        > 0
    )

def list_free_posts(db: Session, current_user_id: str | None) -> list[dict]:
    likes_subq = _likes_expr()
    liked_expr = _liked_by_user_expr(current_user_id)
    query = (
        select(FreeBoardPost, func.coalesce(likes_subq.c.likes, 0).label("likes"), liked_expr.label("liked_by_user"))
        .options(selectinload(FreeBoardPost.comments))
        .outerjoin(likes_subq, FreeBoardPost.id == likes_subq.c.post_id)
        .order_by(FreeBoardPost.created_at.desc())
    )
    rows = db.execute(query).all()
    return [{"post": row[0], "likes": int(row[1] or 0), "liked_by_user": bool(row[2])} for row in rows]

def get_free_post_with_meta(db: Session, post_id: int, current_user_id: str | None) -> dict:
    likes_subq = _likes_expr()
    liked_expr = _liked_by_user_expr(current_user_id)
    query = (
        select(FreeBoardPost, func.coalesce(likes_subq.c.likes, 0).label("likes"), liked_expr.label("liked_by_user"))
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

def create_free_post_comment(db: Session, post_id: int, payload: FreeBoardCommentCreateRequest) -> FreeBoardComment:
    post = db.get(FreeBoardPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    comment = FreeBoardComment(post_id=post_id, author_name=payload.author_name, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

# --- 핵심: 데이터 강제 시드(Seed) 로직 ---

def seed_board_data(db: Session) -> None:
    # 1. 기존 데이터 삭제 (폭파 로직)
    db.query(BoardReview).delete()
    db.query(BoardPerformance).delete()
    db.query(FreeBoardComment).delete()
    db.query(FreeBoardPostLike).delete()
    db.query(FreeBoardPost).delete()
    db.commit()

    # 2. 공연 데이터 생성
    performances = [
        BoardPerformance(
            title="퇴근 후 락 스피릿: 제1회 오피스 락 페스티벌",
            date="2026-03-28", location="서울 강남구 역삼동 라이브클럽 '해방'",
            genre="Rock", artist="부장님 몰래", image_url="/static/uploads/1.png",
            description="서류 가방 대신 기타를 든 직장인들의 반란! 낮에는 평범한 회사원이지만 밤에는 락스타로 변신하는 저희의 무대에 초대합니다."
        ),
        BoardPerformance(
            title="판교 테크노밸리: 코딩하는 어쿠스틱 밤",
            date="2026-04-04", location="경기 성남시 판교 야외 공연장",
            genre="Acoustic", artist="개발자 듀오: 디버그(Debug)", image_url="/static/uploads/2.png",
            description="지친 코딩 끝에 찾아온 감성적인 선율. 퇴근길 가벼운 마음으로 들러주세요."
        ),
        BoardPerformance(
            title="여의도 빌딩 숲 재즈 나잇",
            date="2026-04-11", location="서울 영등포구 여의도 펍 '스톡 마켓'",
            genre="Jazz", artist="금융인 재즈 퀸텟", image_url="/static/uploads/3.png",
            description="숫자와 차트에서 벗어나 즐기는 세련된 재즈의 밤. 고품격 재즈 사운드를 즐겨보세요."
        ),
    ]
    db.add_all(performances)
    db.flush()

    # 3. 후기 데이터 생성 (공연 인덱스 0, 1, 2 사용)
    db.add_all([
        BoardReview(
            performance_id=performances[0].id, author_name="퇴근후기타", rating=5, type="found_member",
            content="AI 매칭 덕분에 성향이 100% 일치하는 드럼 멤버를 구했어요! 일정 잡기가 너무 편합니다.",
            image_urls=["/static/uploads/Gemini_Generated_Band.png"]
        ),
        BoardReview(
            performance_id=performances[0].id, author_name="판교베이스", rating=5, type="joined_club",
            content="활동 목표까지 분석해서 매칭해주니 첫 만남부터 위화감이 없었네요. 즐겁게 합주 중입니다!"
        ),
        BoardReview(
            performance_id=performances[1].id, author_name="여의도색소폰", rating=4, type="found_member",
            content="직장 생활 패턴에 맞춰 주말 오전 합주가 가능한 분들을 딱딱 매칭해줘서 신기했습니다."
        ),
        BoardReview(
            performance_id=performances[2].id, author_name="메탈스피릿", rating=5, type="joined_club",
            content="헤비메탈 취향 저격! AI가 제 취향과 100% 일치하는 팀을 추천해줬어요. 매칭 알고리즘이 정말 정교하네요!",
            image_urls=["/static/uploads/Gemini_Generated_Image_2.png"]
        ),
        BoardReview(
            performance_id=performances[1].id, author_name="역삼동기타맨", rating=5, type="found_member",
            content="강남역 근처 주말 오전 합주 가능한 건반 세션을 찾고 있었는데, AI가 딱 맞는 분을 연결해줬어요."
        ),
    ])

    # 4. 자유게시판 포스트 및 댓글
    posts = [
        FreeBoardPost(author_name="새미", content="밴드 연습 끝났어요. 보컬 한 분 더 구합니다."),
        FreeBoardPost(author_name="혜진", content="첫 무대 공연 끝냈어요. 정말 좋은 경험이었어요."),
        FreeBoardPost(author_name="크리스", content="상태 좋은 앰프 판매합니다. 관심 있으면 DM 주세요."),
    ]
    db.add_all(posts)
    db.flush()

    db.add_all([
        FreeBoardComment(post_id=posts[0].id, author_name="이서연", content="축하해요. 어떤 장르 하시나요?"),
        FreeBoardComment(post_id=posts[1].id, author_name="김하늘", content="멋지네요! 고생하셨습니다."),
    ])
    
    db.commit()