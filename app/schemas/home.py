from datetime import datetime

from pydantic import BaseModel


class ReviewCreateRequest(BaseModel):
    title: str
    body: str


class ReviewOut(BaseModel):
    id: int
    title: str
    body: str
    created_at: datetime


class TeamPromotionCreateRequest(BaseModel):
    team_name: str
    summary: str


class TeamPromotionOut(BaseModel):
    id: int
    team_name: str
    summary: str
    created_at: datetime
