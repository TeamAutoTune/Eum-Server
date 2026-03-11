from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenOut


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
        gender=payload.gender,
        age=payload.age,
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
