from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BoardPerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: str
    location: str
    genre: str
    artist: str
    description: str
    image_url: str | None = None
    created_at: datetime


class BoardReviewCreateRequest(BaseModel):
    performance_id: int
    author_name: str = Field(min_length=1, max_length=100)
    rating: int = Field(ge=1, le=5)
    type: Literal["found_member", "joined_club"]
    content: str = Field(min_length=1)
    image_url: str | None = None


class BoardReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    performance_id: int
    author_name: str
    rating: int
    type: str
    content: str
    image_url: str | None = None
    created_at: datetime


class FreeBoardCommentCreateRequest(BaseModel):
    author_name: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)


class FreeBoardCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    author_name: str
    content: str
    created_at: datetime


class FreeBoardPostCreateRequest(BaseModel):
    author_name: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)


class FreeBoardPostOut(BaseModel):
    id: int
    author_name: str
    content: str
    likes: int
    liked_by_user: bool
    comments_count: int
    comments_list: list[FreeBoardCommentOut]
    created_at: datetime


class FreeBoardLikeToggleResponse(BaseModel):
    post_id: int
    likes: int
    liked_by_user: bool


class DeleteResponse(BaseModel):
    success: bool
