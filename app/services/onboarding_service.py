from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.matching import MatchingProfile
from app.models.team import Team, TeamMember
from app.models.team_matching_profile import TeamMatchingProfile
from app.models.user import User
from app.schemas.onboarding import PersonalOnboardingUpsertRequest, TeamOnboardingUpsertRequest
from app.services.matching_ai_summary_service import generate_profile_summary, generate_team_recruit_summary


logger = logging.getLogger(__name__)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", [], {}):
        return []
    return [value]


def _string_list(value: Any) -> list[str]:
    return [text for item in _safe_list(value) if (text := _safe_text(item))]


def _merge_non_empty(*values: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        for key, item in _safe_dict(value).items():
            if item in (None, "", [], {}):
                continue
            merged[key] = item
    return merged


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _extract_region_fields(data: dict[str, Any]) -> tuple[str, str, str]:
    perf = _safe_dict(data.get("performancePreferences"))
    region = _safe_text(_first_non_empty(data.get("region"), perf.get("activityRegion")))
    if region:
        parts = region.split()
        region_sido = _safe_text(_first_non_empty(data.get("regionSido"), perf.get("activityRegionSido"), parts[0]))
        region_sigungu = _safe_text(
            _first_non_empty(data.get("regionSigungu"), perf.get("activityRegionSigungu"), parts[1] if len(parts) > 1 else "")
        )
        return region, region_sido, region_sigungu
    return "", _safe_text(data.get("regionSido")), _safe_text(data.get("regionSigungu"))


def _extract_activity_goals(data: dict[str, Any]) -> list[str]:
    raw_goal = data.get("activityGoal")
    goal_dict = _safe_dict(raw_goal)
    return _string_list(
        _first_non_empty(
            data.get("goals"),
            data.get("activityGoals"),
            goal_dict.get("activityGoals"),
            raw_goal if isinstance(raw_goal, (list, str)) else None,
        )
    )


def _extract_availability(data: dict[str, Any]) -> list[str]:
    perf = _safe_dict(data.get("performancePreferences"))
    return _string_list(
        _first_non_empty(
            data.get("availability"),
            data.get("availableTimes"),
            perf.get("availableTimeSlots"),
        )
    )


def _normalize_personal_payload(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    region, region_sido, region_sigungu = _extract_region_fields(data)
    activity_goals = _extract_activity_goals(data)
    availability = _extract_availability(data)
    instruments = _string_list(_first_non_empty(data.get("instruments"), data.get("playableInstruments")))
    parts = _string_list(_first_non_empty(data.get("parts"), data.get("primaryParts")))
    genres = _string_list(_first_non_empty(data.get("genres"), data.get("preferredGenres")))
    practice_frequency = _safe_text(
        _first_non_empty(data.get("practiceFrequency"), _safe_dict(data.get("performancePreferences")).get("practiceFrequency"))
    )
    style = _safe_text(_first_non_empty(data.get("style"), _safe_dict(data.get("performancePreferences")).get("performanceStyle")))
    target_level = _safe_text(_first_non_empty(data.get("targetLevel"), data.get("level")))
    lifestyle = _safe_dict(data.get("lifestyle"))
    profile_data = _merge_non_empty(
        data,
        {
            "instruments": instruments,
            "playableInstruments": instruments,
            "parts": parts,
            "primaryParts": parts,
            "genres": genres,
            "preferredGenres": genres,
            "region": region or region_sido,
            "regionSido": region_sido,
            "regionSigungu": region_sigungu,
            "availability": availability,
            "availableTimes": availability,
            "practiceFrequency": practice_frequency,
            "style": style,
            "targetLevel": target_level,
            "goals": activity_goals,
            "activityGoal": {"activityGoals": activity_goals},
            "lifestyle": lifestyle,
            "performancePreferences": {
                "performanceStyle": style,
                "activityRegion": region,
                "activityRegionSido": region_sido,
                "activityRegionSigungu": region_sigungu,
                "availableTimeSlots": availability,
                "practiceFrequency": practice_frequency,
            },
            "matchConditions": {
                "requiredConditions": _string_list(
                    _first_non_empty(_safe_dict(data.get("matchConditions")).get("requiredConditions"), data.get("requiredConditions"))
                ),
                "avoidConditions": _string_list(
                    _first_non_empty(_safe_dict(data.get("matchConditions")).get("avoidConditions"), data.get("avoidConditions"))
                ),
            },
        },
    )
    candidate_data = {
        "instruments": instruments,
        "parts": parts,
        "genres": genres,
        "style": style,
        "region": region or region_sido,
        "regionSido": region_sido,
        "regionSigungu": region_sigungu,
        "availability": availability,
        "practiceFrequency": practice_frequency,
        "targetLevel": target_level,
        "activityGoal": ", ".join(activity_goals),
        "tags": _string_list(data.get("tags")),
    }
    return profile_data, candidate_data


def _normalize_team_payload(
    *,
    team: Team,
    leader_profile: MatchingProfile | None,
    data: dict[str, Any],
    recruit_needs: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_profile = _safe_dict(data.get("teamProfile"))
    region = _safe_text(_first_non_empty(team_profile.get("region"), data.get("region"), team.region))
    region_sido = _safe_text(_first_non_empty(team_profile.get("regionSido"), data.get("regionSido")))
    region_sigungu = _safe_text(_first_non_empty(team_profile.get("regionSigungu"), data.get("regionSigungu")))
    try:
        default_genres = json.loads(team.genres or "[]")
    except (TypeError, ValueError):
        default_genres = []
    if not isinstance(default_genres, list):
        default_genres = []
    genres = _string_list(_first_non_empty(team_profile.get("genres"), data.get("genres"), default_genres))
    activity_goals = _extract_activity_goals(_merge_non_empty(team_profile, data))
    recruiting_sessions = _string_list(
        _first_non_empty(team_profile.get("recruitingSessions"), data.get("recruitingSessions"))
    )
    practice_frequency = _safe_text(
        _first_non_empty(team_profile.get("practiceFrequency"), data.get("practiceFrequency"))
    )
    average_age = _safe_text(_first_non_empty(team_profile.get("averageAge"), data.get("averageAge"), team.average_age))
    normalized_recruit_needs = [item for item in recruit_needs if isinstance(item, dict)]
    normalized_profile = _merge_non_empty(
        data,
        {
            "teamProfile": {
                "teamName": team.team_name,
                "genres": genres,
                "region": region,
                "regionSido": region_sido,
                "regionSigungu": region_sigungu,
                "practiceFrequency": practice_frequency,
                "averageAge": average_age,
                "activityGoal": {"activityGoals": activity_goals},
                "recruitingSessions": recruiting_sessions,
            },
            "genres": genres,
            "region": region,
            "regionSido": region_sido,
            "regionSigungu": region_sigungu,
            "practiceFrequency": practice_frequency,
            "averageAge": average_age,
            "activityGoal": {"activityGoals": activity_goals},
            "recruitNeeds": normalized_recruit_needs,
            "recruitingSessions": recruiting_sessions,
            "leaderProfile": {
                "style": _safe_text(_first_non_empty(
                    _safe_dict(leader_profile.candidate_data if leader_profile else {}).get("style"),
                    _safe_dict(leader_profile.profile_data if leader_profile else {}).get("style"),
                )),
                "performancePreferences": _safe_dict(
                    _safe_dict(leader_profile.profile_data if leader_profile else {}).get("performancePreferences")
                ),
            },
        },
    )
    return normalized_profile, normalized_recruit_needs


def _get_personal_source(payload: PersonalOnboardingUpsertRequest) -> dict[str, Any]:
    return _merge_non_empty(payload.profile_data, payload.candidate_data, payload.model_extra or {})


def _get_team_source(payload: TeamOnboardingUpsertRequest) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    extra = payload.model_extra or {}
    recruit_needs = payload.recruit_needs
    if not recruit_needs:
        recruit_needs = [item for item in _safe_list(extra.get("recruit_needs") or extra.get("recruitNeeds")) if isinstance(item, dict)]
    return _merge_non_empty(payload.profile_data, extra), recruit_needs


def _apply_team_summary(profile_data: dict[str, Any], summary: str | None) -> dict[str, Any]:
    normalized = _safe_dict(profile_data)
    team_profile = _safe_dict(normalized.get("teamProfile"))
    team_profile["ai_summary"] = _safe_text(summary)
    normalized["teamProfile"] = team_profile
    return normalized


def upsert_personal_onboarding(
    db: Session,
    user: User,
    payload: PersonalOnboardingUpsertRequest,
    *,
    auto_commit: bool = True,
) -> MatchingProfile:
    source = _get_personal_source(payload)
    profile_data, candidate_data = _normalize_personal_payload(source)

    profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
    if not profile:
        profile = MatchingProfile(user_id=user.id, profile_data=profile_data, candidate_data=candidate_data)
        db.add(profile)
    else:
        profile.profile_data = profile_data
        profile.candidate_data = candidate_data
        profile.profile_summary = None

    primary_instrument = instruments[0] if (instruments := _string_list(candidate_data.get("instruments"))) else None
    if primary_instrument:
        user.instrument = primary_instrument

    if auto_commit:
        db.commit()
        db.refresh(profile)
    else:
        db.flush()

    try:
        profile_summary = generate_profile_summary(
            profile_data=profile.profile_data or {},
            candidate_data=profile.candidate_data or {},
        )
        if profile_summary:
            profile.profile_summary = profile_summary
            next_candidate_data = _safe_dict(profile.candidate_data)
            next_candidate_data["ai_summary"] = profile_summary
            profile.candidate_data = next_candidate_data
            if auto_commit:
                db.commit()
                db.refresh(profile)
            else:
                db.flush()
    except Exception:
        if auto_commit:
            db.rollback()
        logger.exception("profile_summary generation failed after personal onboarding save user_id=%s", user.id)
    return profile


def upsert_team_onboarding(
    db: Session,
    *,
    team_id: int,
    current_user: User,
    payload: TeamOnboardingUpsertRequest,
    auto_commit: bool = True,
) -> TeamMatchingProfile:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    if team.leader_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team leaders can update team onboarding")

    membership = db.scalar(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == current_user.id))
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current user is not a team member")

    source, recruit_needs = _get_team_source(payload)
    leader_profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == current_user.id))
    profile_data, normalized_recruit_needs = _normalize_team_payload(
        team=team,
        leader_profile=leader_profile,
        data=source,
        recruit_needs=recruit_needs,
    )

    profile = db.scalar(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id == team.id))
    if not profile:
        profile = TeamMatchingProfile(
            team_id=team.id,
            profile_data=profile_data,
            recruit_needs=normalized_recruit_needs,
        )
        db.add(profile)
    else:
        profile.profile_data = profile_data
        profile.recruit_needs = normalized_recruit_needs
        profile.recruit_summary = None

    if auto_commit:
        db.commit()
        db.refresh(profile)
    else:
        db.flush()

    try:
        recruit_summary = generate_team_recruit_summary(
            profile_data=profile.profile_data or {},
            recruit_needs=profile.recruit_needs or [],
        )
        if recruit_summary:
            profile.recruit_summary = recruit_summary
            profile.profile_data = _apply_team_summary(profile.profile_data or {}, recruit_summary)
            if auto_commit:
                db.commit()
                db.refresh(profile)
            else:
                db.flush()
    except Exception:
        if auto_commit:
            db.rollback()
        logger.exception("recruit_summary generation failed after team onboarding save team_id=%s", team.id)
    return profile
