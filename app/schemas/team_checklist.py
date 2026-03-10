from datetime import datetime

from pydantic import BaseModel, Field


class TeamChecklistCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class TeamChecklistUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    is_checked: bool | None = None


class TeamChecklistResponse(BaseModel):
    checklist_id: int
    team_id: int
    content: str
    is_checked: bool
    created_at: datetime
    updated_at: datetime
