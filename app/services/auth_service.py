from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenOut

_TEST_PATTERNS = ("test", "dummy", "seed", "sample", "demo")


def count_users(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def count_user_stats(db: Session) -> dict[str, int]:
    total_users = count_users(db)
    seeded_test_users = db.scalar(
        select(func.count()).select_from(User).where(func.lower(User.user_id).like("seed_test_%"))
    ) or 0

    heuristic_conditions = [
        func.lower(User.user_id).like(f"%{pattern}%") for pattern in _TEST_PATTERNS
    ] + [
        func.lower(User.nickname).like(f"%{pattern}%") for pattern in _TEST_PATTERNS
    ]
    heuristic_test_users = db.scalar(
        select(func.count())
        .select_from(User)
        .where(or_(*heuristic_conditions))
        .where(~func.lower(User.user_id).like("seed_test_%"))
    ) or 0

    return {
        "total_users": total_users,
        "seeded_test_users": seeded_test_users,
        "heuristic_test_users": heuristic_test_users,
        "probable_real_signup_users": max(total_users - seeded_test_users - heuristic_test_users, 0),
    }


def signup(db: Session, payload: SignupRequest) -> TokenOut:
    existing_user_id = db.scalar(select(User).where(User.user_id == payload.user_id))
    if existing_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id already exists")

    existing_nickname = db.scalar(select(User).where(User.nickname == payload.nickname))
    if existing_nickname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="nickname already exists")

    user = User(
        nickname=payload.nickname,
        user_id=payload.user_id,
        hashed_password=hash_password(payload.password),
        instrument=payload.instrument,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return TokenOut(access_token=token, user=user)


def login(db: Session, payload: LoginRequest) -> TokenOut:
    user = db.scalar(select(User).where(User.user_id == payload.user_id))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=user.id)
    return TokenOut(access_token=token, user=user)
