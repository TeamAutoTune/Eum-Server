from datetime import datetime

from pydantic import BaseModel, Field


class TeamNoticeCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class TeamNoticeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)


class TeamNoticeResponse(BaseModel):
    notice_id: int
    team_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
