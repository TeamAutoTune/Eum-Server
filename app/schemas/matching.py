from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MatchingRecommendRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["apply", "recruit"] = "apply"
    ranking_version: str = "hybrid_v1"
    min_score: int = 0
    limit: int = 10
    recruit_needs: list[dict[str, Any]] = Field(default_factory=list)
    hard_filters: dict[str, Any] = Field(default_factory=dict)


class MatchingProfileSaveRequest(BaseModel):
    profile_data: dict[str, Any] = Field(default_factory=dict)
    candidate_data: dict[str, Any] = Field(default_factory=dict)


class TeamMatchingProfileSaveRequest(BaseModel):
    team_id: int
    profile_data: dict[str, Any] = Field(default_factory=dict)
    recruit_needs: list[dict[str, Any]] = Field(default_factory=list)


class MatchingResultOut(BaseModel):
    recommendation_id: str
    rank_position: int
    id: str
    nickname: str
    team_name: str = ""
    teamProfile: dict[str, Any] = Field(default_factory=dict)
    leaderProfile: dict[str, Any] = Field(default_factory=dict)
    recruitNeeds: list[dict[str, Any]] = Field(default_factory=list)
    recruitingSessions: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    parts: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    style: str = ""
    region: str = ""
    averageAge: str = ""
    availability: list[str] = Field(default_factory=list)
    practiceFrequency: str = ""
    targetLevel: str = ""
    activityGoal: str = ""
    tags: list[str] = Field(default_factory=list)
    matchScore: int
    reasons: list[str] = Field(default_factory=list)
    ai_summary: str | None = None


class MatchingRecommendResponse(BaseModel):
    recommendation_id: str
    ranking_version: str
    results: list[MatchingResultOut] = Field(default_factory=list)
    debug_code: str | None = None
    debug_message: str | None = None


class MatchingProfileSaveResponse(BaseModel):
    user_id: str
    profile_data: dict[str, Any] = Field(default_factory=dict)
    candidate_data: dict[str, Any] = Field(default_factory=dict)
    ai_summary: str | None = None


class TeamMatchingProfileSaveResponse(BaseModel):
    team_id: int
    profile_data: dict[str, Any] = Field(default_factory=dict)
    recruit_needs: list[dict[str, Any]] = Field(default_factory=list)
    ai_summary: str | None = None


class MatchingEventRequest(BaseModel):
    candidate_id: str
    recommendation_id: str
    event_type: str
    mode: Literal["apply", "recruit"] = "apply"
    matchScore: int | None = None
    rank_position: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
