from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PersonalOnboardingUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    profile_data: dict[str, Any] = Field(default_factory=dict)
    candidate_data: dict[str, Any] = Field(default_factory=dict)


class TeamOnboardingUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    profile_data: dict[str, Any] = Field(default_factory=dict)
    recruit_needs: list[dict[str, Any]] = Field(default_factory=list)


class OnboardingUpsertResponse(BaseModel):
    ok: bool = True
    profile_id: int
    summary: dict[str, Any] = Field(default_factory=dict)
