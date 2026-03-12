from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.matching import MatchingProfile
from app.models.team import Team, TeamMember
from app.models.team_matching_profile import TeamMatchingProfile
from app.services.matching_ai_summary_service import generate_profile_summary, generate_team_recruit_summary

logger = logging.getLogger(__name__)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_of_dict(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _profile_to_candidate_data(profile_data: dict[str, Any], existing_candidate_data: dict[str, Any]) -> dict[str, Any]:
    merged = {**_safe_dict(profile_data), **_safe_dict(existing_candidate_data)}
    performance_preferences = _safe_dict(merged.get("performancePreferences"))
    activity_goal = _safe_dict(merged.get("activityGoal"))

    return {
        "instruments": merged.get("instruments") or merged.get("playableInstruments") or [],
        "parts": merged.get("parts") or merged.get("primaryParts") or [],
        "genres": merged.get("genres") or merged.get("preferredGenres") or [],
        "style": merged.get("style") or performance_preferences.get("performanceStyle") or "",
        "region": merged.get("region") or performance_preferences.get("activityRegion") or "",
        "availability": (
            merged.get("availability")
            or merged.get("availableTimes")
            or performance_preferences.get("availableTimeSlots")
            or []
        ),
        "practiceFrequency": merged.get("practiceFrequency") or performance_preferences.get("practiceFrequency") or "",
        "activityGoal": activity_goal or merged.get("activityGoal") or merged.get("goals") or merged.get("activityGoals") or "",
        "targetLevel": merged.get("targetLevel") or "",
        "tags": merged.get("tags") or [],
        "recruitNeeds": merged.get("recruitNeeds") or [],
        "recruitingSessions": merged.get("recruitingSessions") or merged.get("recruiting_sessions") or [],
    }


def _can_edit_team_profile(db: Session, user_id: str, team_id: int) -> bool:
    team = db.get(Team, team_id)
    if not team:
        return False

    if team.leader_id == user_id:
        return True

    member = db.scalar(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    return member is not None


def upsert_user_matching_profile(
    db: Session,
    *,
    user_id: str,
    profile_data: dict[str, Any],
    candidate_data: dict[str, Any],
) -> MatchingProfile:
    normalized_profile_data = _safe_dict(profile_data)
    normalized_candidate_data = _profile_to_candidate_data(normalized_profile_data, _safe_dict(candidate_data))

    row = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user_id))
    if not row:
        row = MatchingProfile(
            user_id=user_id,
            profile_data=normalized_profile_data,
            candidate_data=normalized_candidate_data,
            profile_summary=None,
        )
        db.add(row)
    else:
        row.profile_data = normalized_profile_data
        row.candidate_data = normalized_candidate_data
        row.profile_summary = None

    db.commit()
    db.refresh(row)

    try:
        profile_summary = generate_profile_summary(
            profile_data=row.profile_data or {},
            candidate_data=row.candidate_data or {},
        )
        if profile_summary:
            row.profile_summary = profile_summary
            db.commit()
            db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("profile_summary generation failed after profile save user_id=%s", user_id)

    return row


def upsert_team_matching_profile(
    db: Session,
    *,
    user_id: str,
    team_id: int,
    profile_data: dict[str, Any],
    recruit_needs: list[dict[str, Any]],
) -> TeamMatchingProfile:
    if not _can_edit_team_profile(db, user_id=user_id, team_id=team_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to edit this team profile")

    normalized_profile_data = _safe_dict(profile_data)
    normalized_recruit_needs = _safe_list_of_dict(recruit_needs)

    row = db.scalar(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id == team_id))
    if not row:
        row = TeamMatchingProfile(
            team_id=team_id,
            profile_data=normalized_profile_data,
            recruit_needs=normalized_recruit_needs,
            recruit_summary=None,
        )
        db.add(row)
    else:
        row.profile_data = normalized_profile_data
        row.recruit_needs = normalized_recruit_needs
        row.recruit_summary = None

    db.commit()
    db.refresh(row)

    try:
        recruit_summary = generate_team_recruit_summary(
            profile_data=row.profile_data or {},
            recruit_needs=row.recruit_needs or [],
        )
        if recruit_summary:
            row.recruit_summary = recruit_summary
            db.commit()
            db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("recruit_summary generation failed after team profile save team_id=%s", team_id)

    return row
