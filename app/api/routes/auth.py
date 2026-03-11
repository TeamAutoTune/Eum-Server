from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenOut, UserCountOut, UserCountStatsOut
from app.schemas.common import UserOut
from app.services import auth_service

router = APIRouter()


@router.get("/count", response_model=UserCountOut)
def count_users(db: Session = Depends(get_db)):
    return UserCountOut(count=auth_service.count_users(db))


@router.get("/count-stats", response_model=UserCountStatsOut)
def count_user_stats(db: Session = Depends(get_db)):
    return UserCountStatsOut(**auth_service.count_user_stats(db))


@router.post("/signup", response_model=TokenOut)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    return auth_service.signup(db, payload)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, payload)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
