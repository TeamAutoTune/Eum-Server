from pydantic import BaseModel, Field

from app.schemas.common import UserOut


class SignupRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=30)
    user_id: str = Field(min_length=4, max_length=30)
    password: str = Field(min_length=4, max_length=128)
    instrument: str = Field(default="Unknown", min_length=1, max_length=50)
    gender: str | None = Field(default=None, max_length=20)
    age: int | None = Field(default=None, ge=0, le=120)


class LoginRequest(BaseModel):
    user_id: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
