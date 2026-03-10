from datetime import datetime

from pydantic import BaseModel, Field


class TeamScheduleCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    start_at: datetime
    end_at: datetime


class TeamScheduleUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class TeamScheduleResponse(BaseModel):
    schedule_id: int
    team_id: int
    title: str
    description: str
    start_at: datetime
    end_at: datetime
    created_at: datetime
    updated_at: datetime
