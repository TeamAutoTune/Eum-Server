from __future__ import annotations

import logging
import random
import sys
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.matching import MatchingProfile
from app.models.team import Team, TeamMember
from app.models.team_matching_profile import TeamMatchingProfile
from app.models.user import User
from app.services import chat_service
from app.services.recommendation_logging import log_match_event, log_match_features


logger = logging.getLogger(__name__)

_BAND_MATCHING_CANDIDATE_PATHS = [
    Path(__file__).resolve().parents[2] / "band_matching",
    Path(__file__).resolve().parents[3] / "band_matching",
]
DEFAULT_RANKING_VERSION = "hybrid_v1"
FALLBACK_RANKING_VERSION = "rule_fallback_v1"


def _safe_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_deepcopy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return value


def _norm_text(value: Any) -> str:
    return _safe_text(value).lower()


def _setify(value: Any) -> set[str]:
    return {_norm_text(item) for item in _safe_list(value) if _norm_text(item)}


def _overlap_ratio(left: Any, right: Any) -> float:
    set_left = _setify(left)
    set_right = _setify(right)
    if not set_left or not set_right:
        return 0.0
    return len(set_left & set_right) / max(len(set_left), len(set_right))


def _extract_region_parts(region: str) -> tuple[str, str]:
    parts = _safe_text(region).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return _norm_text(parts[0]), ""
    return _norm_text(parts[0]), _norm_text(parts[1])


def _normalized_list_from(value: Any) -> list[str]:
    return [_norm_text(v) for v in _safe_list(value) if _norm_text(v)]


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _merge_missing_dict(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = _safe_dict(_safe_deepcopy(base))
    for key, extra_value in _safe_dict(extra).items():
        current_value = merged.get(key)
        if isinstance(current_value, dict) and isinstance(extra_value, dict):
            merged[key] = _merge_missing_dict(current_value, extra_value)
            continue
        if current_value in (None, "", [], {}):
            merged[key] = _safe_deepcopy(extra_value)
    return merged


def _extract_activity_goals_raw(data: dict[str, Any]) -> list[Any]:
    activity_goal_raw = data.get("activityGoal")
    activity_goal = _safe_dict(activity_goal_raw)
    goals = _safe_list(
        _first_non_empty(
            data.get("goals"),
            data.get("activityGoals"),
            activity_goal.get("activityGoals"),
            data.get("activity_goal"),
            activity_goal_raw if isinstance(activity_goal_raw, (str, list)) else None,
        )
    )
    return goals


def _extract_recruit_needs_raw(data: dict[str, Any]) -> list[dict[str, Any]]:
    needs = _safe_list(_first_non_empty(data.get("recruitNeeds"), data.get("recruit_needs")))
    return [item for item in needs if isinstance(item, dict)]


def _extract_recruiting_sessions_raw(
    data: dict[str, Any],
    *,
    fallback_to_instruments: bool = False,
) -> list[Any]:
    explicit = _safe_list(_first_non_empty(data.get("recruitingSessions"), data.get("recruiting_sessions")))
    if explicit:
        return explicit

    recruit_needs = _extract_recruit_needs_raw(data)
    derived = [need.get("instrument") for need in recruit_needs if _safe_text(need.get("instrument"))]
    if derived:
        return derived

    if fallback_to_instruments:
        return _safe_list(_first_non_empty(data.get("instruments"), data.get("playableInstruments")))

    return []


def _extract_region_fields(data: dict[str, Any]) -> tuple[str, str, str]:
    perf = _safe_dict(data.get("performancePreferences"))
    region_text = _safe_text(
        _first_non_empty(
            data.get("region"),
            perf.get("activityRegion"),
        )
    )
    parsed_sido, parsed_sigungu = _extract_region_parts(region_text)
    region_sido = _safe_text(
        _first_non_empty(
            data.get("regionSido"),
            data.get("region_sido"),
            perf.get("activityRegionSido"),
            parsed_sido,
        )
    )
    region_sigungu = _safe_text(
        _first_non_empty(
            data.get("regionSigungu"),
            data.get("region_sigungu"),
            perf.get("activityRegionSigungu"),
            parsed_sigungu,
        )
    )
    return region_text, region_sido, region_sigungu


def _extract_lifestyle_fields(data: dict[str, Any]) -> dict[str, Any]:
    lifestyle = _safe_dict(data.get("lifestyle"))
    return {
        "drink": _safe_text(_first_non_empty(lifestyle.get("drink"), data.get("drink"))),
        "smoking": _safe_text(_first_non_empty(lifestyle.get("smoking"), data.get("smoking"))),
        "social": _safe_text(_first_non_empty(lifestyle.get("social"), data.get("social"))),
        "meal": _safe_text(_first_non_empty(lifestyle.get("meal"), data.get("meal"))),
    }


def _build_leader_profile_data(profile_data: dict[str, Any], candidate_data: dict[str, Any]) -> dict[str, Any]:
    lifestyle = _extract_lifestyle_fields(profile_data or candidate_data or {})
    performance_preferences = _safe_dict(profile_data.get("performancePreferences"))
    return {
        "style": _safe_text(
            _first_non_empty(
                candidate_data.get("style"),
                performance_preferences.get("performanceStyle"),
            )
        ),
        "lifestyle": lifestyle,
        "performancePreferences": {
            "performanceStyle": _safe_text(performance_preferences.get("performanceStyle")),
            "activityRegion": _safe_text(performance_preferences.get("activityRegion")),
            "activityRegionSido": _safe_text(performance_preferences.get("activityRegionSido")),
            "activityRegionSigungu": _safe_text(performance_preferences.get("activityRegionSigungu")),
            "availableTimeSlots": _safe_list(performance_preferences.get("availableTimeSlots")),
            "practiceFrequency": _safe_text(performance_preferences.get("practiceFrequency")),
        },
    }


def _team_to_profile_data(team: Team, team_matching_profile: TeamMatchingProfile | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stored_profile = _safe_dict(team_matching_profile.profile_data if team_matching_profile else {})
    stored_team_profile = _safe_dict(stored_profile.get("teamProfile"))
    recruit_summary = _safe_text(team_matching_profile.recruit_summary if team_matching_profile else "")
    try:
        team_genres = json.loads(team.genres or "[]")
        if not isinstance(team_genres, list):
            team_genres = []
    except (TypeError, json.JSONDecodeError):
        team_genres = []
    recruit_needs = _safe_list(team_matching_profile.recruit_needs if team_matching_profile else [])
    team_profile = {
        "teamProfile": {
            "teamName": team.team_name,
            "ai_summary": _safe_text(_first_non_empty(stored_team_profile.get("ai_summary"), recruit_summary)),
            "genres": _safe_list(_first_non_empty(stored_team_profile.get("genres"), stored_profile.get("genres"), team_genres)),
            "practiceFrequency": _safe_text(
                _first_non_empty(stored_team_profile.get("practiceFrequency"), stored_profile.get("practiceFrequency"))
            ),
            "region": _safe_text(_first_non_empty(stored_team_profile.get("region"), stored_profile.get("region"), team.region)),
            "regionSido": _safe_text(_first_non_empty(stored_team_profile.get("regionSido"), stored_profile.get("regionSido"))),
            "regionSigungu": _safe_text(_first_non_empty(stored_team_profile.get("regionSigungu"), stored_profile.get("regionSigungu"))),
            "averageAge": _safe_text(_first_non_empty(stored_team_profile.get("averageAge"), stored_profile.get("averageAge"), team.average_age)),
            "activityGoal": {
                "activityGoals": _safe_list(
                    _first_non_empty(
                        _safe_dict(stored_team_profile.get("activityGoal")).get("activityGoals"),
                        _safe_dict(stored_profile.get("activityGoal")).get("activityGoals"),
                    )
                ),
            },
            "recruitingSessions": _safe_list(
                _first_non_empty(stored_team_profile.get("recruitingSessions"), stored_profile.get("recruitingSessions"))
            ),
        },
        "genres": _safe_list(_first_non_empty(stored_profile.get("genres"), team_genres)),
        "practiceFrequency": _safe_text(_first_non_empty(stored_profile.get("practiceFrequency"), stored_team_profile.get("practiceFrequency"))),
        "region": _safe_text(_first_non_empty(stored_profile.get("region"), stored_team_profile.get("region"), team.region)),
        "regionSido": _safe_text(_first_non_empty(stored_profile.get("regionSido"), stored_team_profile.get("regionSido"))),
        "regionSigungu": _safe_text(_first_non_empty(stored_profile.get("regionSigungu"), stored_team_profile.get("regionSigungu"))),
        "averageAge": _safe_text(_first_non_empty(stored_profile.get("averageAge"), stored_team_profile.get("averageAge"), team.average_age)),
        "activityGoal": {
            "activityGoals": _safe_list(
                _first_non_empty(
                    _safe_dict(stored_profile.get("activityGoal")).get("activityGoals"),
                    _safe_dict(stored_team_profile.get("activityGoal")).get("activityGoals"),
                )
            ),
        },
        "recruitingSessions": _safe_list(
            _first_non_empty(stored_profile.get("recruitingSessions"), stored_team_profile.get("recruitingSessions"))
        ),
        "recruitNeeds": [item for item in recruit_needs if isinstance(item, dict)],
    }
    return team_profile, team_profile["recruitNeeds"]


def _get_viewer_matching_profile(db: Session, viewer_id: str | None) -> MatchingProfile | None:
    if not viewer_id or viewer_id == "anonymous":
        return None
    return db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == viewer_id))


def _get_viewer_team_context(
    db: Session,
    viewer_id: str | None,
) -> tuple[Team | None, TeamMatchingProfile | None]:
    if not viewer_id or viewer_id == "anonymous":
        return None, None

    team = db.scalar(
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == viewer_id)
        .order_by(Team.created_at.desc())
    )
    if not team:
        team = db.scalar(select(Team).where(Team.leader_id == viewer_id).order_by(Team.created_at.desc()))
    if not team:
        return None, None

    team_profile = db.scalar(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id == team.id))
    return team, team_profile


def _enrich_request_profile(
    db: Session,
    profile: dict[str, Any],
    recruit_needs: list[dict[str, Any]],
    viewer_id: str | None,
    mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    merged_profile = _safe_dict(_safe_deepcopy(profile))
    merged_recruit_needs = [item for item in recruit_needs if isinstance(item, dict)]

    viewer_matching_profile = _get_viewer_matching_profile(db, viewer_id)
    if viewer_matching_profile:
        merged_profile = _merge_missing_dict(merged_profile, viewer_matching_profile.profile_data or {})
        merged_profile = _merge_missing_dict(merged_profile, viewer_matching_profile.candidate_data or {})
        merged_profile = _merge_missing_dict(
            merged_profile,
            {
                "leaderProfile": _build_leader_profile_data(
                    viewer_matching_profile.profile_data or {},
                    viewer_matching_profile.candidate_data or {},
                )
            },
        )

    if mode != "recruit":
        return merged_profile, merged_recruit_needs

    team, team_matching_profile = _get_viewer_team_context(db, viewer_id)
    if not team:
        return merged_profile, merged_recruit_needs

    team_profile_data, stored_recruit_needs = _team_to_profile_data(team, team_matching_profile)
    merged_profile = _merge_missing_dict(merged_profile, team_profile_data)
    if not merged_recruit_needs:
        merged_recruit_needs = stored_recruit_needs
    if not merged_profile.get("recruitNeeds"):
        merged_profile["recruitNeeds"] = _safe_deepcopy(merged_recruit_needs)
    return merged_profile, merged_recruit_needs


def _build_engine_payload(
    data: dict[str, Any],
    *,
    fallback_to_instruments_for_recruiting: bool = False,
) -> dict[str, Any]:
    data = data or {}
    team_profile = _safe_dict(data.get("teamProfile"))
    leader_profile = _safe_dict(data.get("leaderProfile"))
    merged = dict(data)
    merged.update(team_profile)

    perf = _safe_dict(merged.get("performancePreferences"))
    match_conditions = _safe_dict(merged.get("matchConditions"))
    region_text, region_sido, region_sigungu = _extract_region_fields(merged)
    activity_goals = _extract_activity_goals_raw(merged)
    recruit_needs = _extract_recruit_needs_raw(merged)
    recruiting_sessions = _extract_recruiting_sessions_raw(
        merged,
        fallback_to_instruments=fallback_to_instruments_for_recruiting,
    )
    instruments = _safe_list(_first_non_empty(merged.get("instruments"), merged.get("playableInstruments")))
    parts = _safe_list(_first_non_empty(merged.get("parts"), merged.get("primaryParts")))
    genres = _safe_list(_first_non_empty(merged.get("genres"), merged.get("preferredGenres")))
    availability = _safe_list(
        _first_non_empty(
            merged.get("availableTimes"),
            merged.get("availability"),
            perf.get("availableTimeSlots"),
        )
    )
    practice_frequency = _safe_text(
        _first_non_empty(
            merged.get("practiceFrequency"),
            perf.get("practiceFrequency"),
        )
    )
    style = _safe_text(
        _first_non_empty(
            merged.get("style"),
            perf.get("performanceStyle"),
            leader_profile.get("style"),
            _safe_dict(leader_profile.get("performancePreferences")).get("performanceStyle"),
        )
    )
    age_group = _safe_text(_first_non_empty(merged.get("ageGroup"), merged.get("averageAge")))
    lifestyle = _extract_lifestyle_fields(merged)
    if not any(lifestyle.values()) and leader_profile:
        lifestyle = _extract_lifestyle_fields(leader_profile)

    normalized = dict(merged)
    normalized["instruments"] = instruments
    normalized["playableInstruments"] = instruments
    normalized["parts"] = parts
    normalized["primaryParts"] = parts
    normalized["genres"] = genres
    normalized["preferredGenres"] = genres
    normalized["goals"] = activity_goals
    normalized["activityGoal"] = {"activityGoals": activity_goals}
    normalized["availability"] = availability
    normalized["availableTimes"] = availability
    normalized["practiceFrequency"] = practice_frequency
    normalized["style"] = style
    normalized["region"] = region_text or region_sido
    normalized["regionSido"] = region_sido
    normalized["regionSigungu"] = region_sigungu
    normalized["ageGroup"] = age_group
    if not normalized.get("averageAge"):
        normalized["averageAge"] = age_group
    normalized["lifestyle"] = lifestyle
    normalized["recruitNeeds"] = recruit_needs
    normalized["recruitingSessions"] = recruiting_sessions
    normalized["performancePreferences"] = {
        "performanceStyle": style,
        "activityRegion": region_text,
        "activityRegionSido": region_sido,
        "activityRegionSigungu": region_sigungu,
        "availableTimeSlots": availability,
        "practiceFrequency": practice_frequency,
    }
    normalized["matchConditions"] = {
        "requiredConditions": _safe_list(
            _first_non_empty(
                match_conditions.get("requiredConditions"),
                data.get("requiredConditions"),
            )
        ),
        "avoidConditions": _safe_list(
            _first_non_empty(
                match_conditions.get("avoidConditions"),
                data.get("avoidConditions"),
            )
        ),
    }
    return normalized


def _load_band_matching() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any], Callable[..., Any], Callable[..., Any], bool]:
    for module_path in _BAND_MATCHING_CANDIDATE_PATHS:
        if not module_path.exists():
            continue

        try:
            if str(module_path) not in sys.path:
                sys.path.insert(0, str(module_path))

            from match_engine import _extract_apply_features  # type: ignore
            from match_engine import _extract_recruit_features  # type: ignore
            from match_engine import get_top_matches  # type: ignore
            from match_engine import normalize_profile  # type: ignore
            from synthetic_data import generate_candidates  # type: ignore

            logger.info("Using external band_matching module from %s", module_path)
            return (
                get_top_matches,
                generate_candidates,
                normalize_profile,
                _extract_apply_features,
                _extract_recruit_features,
                False,
            )
        except Exception:
            logger.exception("Failed to load band_matching module from %s", module_path)

    logger.warning("band_matching module unavailable. Using built-in rule fallback matcher.")
    return (
        _get_top_matches_fallback,
        _generate_candidates_fallback,
        _normalize_profile_fallback,
        _extract_apply_features_fallback,
        _extract_recruit_features_fallback,
        True,
    )


def _generate_candidates_fallback(n: int = 100, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    instruments = ["guitar", "bass", "drum", "vocal", "keyboard"]
    parts = ["lead", "rhythm", "main", "sub"]
    genres = ["rock", "pop", "jazz", "indie", "metal", "ballad"]
    styles = ["band", "busking", "hobby", "pro"]
    regions = [
        ("Seoul", "Gangnam"),
        ("Seoul", "Mapo"),
        ("Gyeonggi", "Suwon"),
        ("Busan", "Haeundae"),
    ]
    slots = ["weekday_evening", "weekend_day", "weekend_evening"]
    frequencies = ["weekly_1", "weekly_2", "weekly_3_plus"]
    goals = ["hobby", "busking", "band", "pro"]

    candidates: list[dict] = []
    for idx in range(1, n + 1):
        sido, sigungu = rng.choice(regions)
        inst_count = rng.choice([1, 2])
        picked_instruments = rng.sample(instruments, k=inst_count)

        candidates.append(
            {
                "id": f"fallback_{idx:03d}",
                "nickname": f"FallbackUser{idx:03d}",
                "instruments": picked_instruments,
                "parts": [rng.choice(parts) for _ in picked_instruments],
                "genres": rng.sample(genres, k=2),
                "style": rng.choice(styles),
                "region": f"{sido} {sigungu}",
                "regionSido": sido,
                "regionSigungu": sigungu,
                "availability": rng.sample(slots, k=2),
                "practiceFrequency": rng.choice(frequencies),
                "targetLevel": "intermediate",
                "activityGoal": rng.choice(goals),
                "tags": [],
            }
        )

    return candidates


def _normalize_profile_fallback(profile_data: dict) -> dict:
    profile_data = profile_data or {}
    perf = profile_data.get("performancePreferences") or {}
    goal = profile_data.get("activityGoal") or {}

    return {
        "playableInstruments": _safe_list(profile_data.get("playableInstruments")),
        "primaryParts": _safe_list(profile_data.get("primaryParts")),
        "preferredGenres": _safe_list(profile_data.get("preferredGenres")),
        "performancePreferences": {
            "activityRegion": _safe_text(perf.get("activityRegion")),
            "activityRegionSido": _safe_text(perf.get("activityRegionSido")),
            "activityRegionSigungu": _safe_text(perf.get("activityRegionSigungu")),
            "availableTimeSlots": _safe_list(perf.get("availableTimeSlots")),
            "practiceFrequency": _safe_text(perf.get("practiceFrequency")),
            "performanceStyle": _safe_text(perf.get("performanceStyle")),
        },
        "activityGoal": {
            "activityGoals": _safe_list(goal.get("activityGoals")),
        },
        "recruitNeeds": _safe_list(profile_data.get("recruitNeeds")),
    }


def _extract_apply_features_fallback(profile: dict, candidate: dict) -> dict[str, float]:
    perf = profile.get("performancePreferences") or {}
    goals = profile.get("activityGoal") or {}

    profile_sido = _safe_text(perf.get("activityRegionSido"))
    candidate_sido = _safe_text(candidate.get("regionSido"))

    profile_freq = _safe_text(perf.get("practiceFrequency"))
    candidate_freq = _safe_text(candidate.get("practiceFrequency"))

    profile_style = _safe_text(perf.get("performanceStyle"))
    candidate_style = _safe_text(candidate.get("style"))

    goal_overlap = _overlap_ratio(goals.get("activityGoals"), [candidate.get("activityGoal")])

    return {
        "instrument_overlap": 1.0 if _setify(profile.get("playableInstruments")) & _setify(candidate.get("instruments")) else 0.0,
        "genre_overlap_ratio": _overlap_ratio(profile.get("preferredGenres"), candidate.get("genres")),
        "part_overlap_ratio": _overlap_ratio(profile.get("primaryParts"), candidate.get("parts")),
        "time_overlap_ratio": _overlap_ratio(perf.get("availableTimeSlots"), candidate.get("availability")),
        "practice_similarity": 1.0 if profile_freq and candidate_freq and profile_freq == candidate_freq else 0.0,
        "goal_similarity": goal_overlap,
        "region_sido_match": 1.0 if profile_sido and candidate_sido and profile_sido == candidate_sido else 0.0,
        "style_match": 1.0 if profile_style and candidate_style and profile_style == candidate_style else 0.0,
    }


def _extract_recruit_features_fallback(profile: dict, candidate: dict, recruit_needs: list[dict]) -> dict[str, float]:
    base = _extract_apply_features_fallback(profile, candidate)

    normalized_needs = [need for need in recruit_needs if isinstance(need, dict)]
    if normalized_needs:
        coverage = 0.0
        for need in normalized_needs:
            inst = _safe_text(need.get("instrument"))
            part = _safe_text(need.get("part"))
            inst_ok = not inst or inst in _setify(candidate.get("instruments"))
            part_ok = not part or part in _setify(candidate.get("parts"))
            coverage += 1.0 if inst_ok and part_ok else 0.0
        recruit_coverage = coverage / len(normalized_needs)
    else:
        recruit_coverage = 0.0

    base["recruit_needs_coverage"] = recruit_coverage
    return base


def _score_from_features_fallback(features: dict[str, float], mode: str) -> int:
    score = (
        features.get("instrument_overlap", 0.0) * 18
        + features.get("genre_overlap_ratio", 0.0) * 24
        + features.get("part_overlap_ratio", 0.0) * 16
        + features.get("time_overlap_ratio", 0.0) * 16
        + features.get("practice_similarity", 0.0) * 8
        + features.get("goal_similarity", 0.0) * 8
        + features.get("region_sido_match", 0.0) * 6
        + features.get("style_match", 0.0) * 4
    )
    if mode == "recruit":
        score += features.get("recruit_needs_coverage", 0.0) * 20
    return max(0, min(100, int(round(score))))


def _reasons_from_features_fallback(features: dict[str, float]) -> list[str]:
    reasons: list[str] = []
    if features.get("instrument_overlap", 0.0) > 0:
        reasons.append("악기 호환")
    if features.get("genre_overlap_ratio", 0.0) >= 0.5:
        reasons.append("장르 취향 유사")
    if features.get("time_overlap_ratio", 0.0) >= 0.5:
        reasons.append("시간대 일치")
    if features.get("region_sido_match", 0.0) > 0:
        reasons.append("활동 지역 일치")
    if not reasons:
        reasons.append("기본 조건 충족")
    return reasons


def _get_top_matches_fallback(
    profile_data: dict,
    candidates: list[dict],
    mode: str = "apply",
    min_score: int = 0,
    top_k: int = 20,
    viewer_id: str = "anonymous",
    enable_feature_logging: bool = False,
) -> list[dict]:
    del viewer_id, enable_feature_logging

    normalized = _normalize_profile_fallback(profile_data)
    results: list[dict] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        if mode == "recruit":
            features = _extract_recruit_features_fallback(
                normalized,
                candidate,
                normalized.get("recruitNeeds", []),
            )
        else:
            features = _extract_apply_features_fallback(normalized, candidate)

        score = _score_from_features_fallback(features, mode)
        if score < min_score:
            continue

        results.append(
            {
                "id": _safe_text(candidate.get("id")),
                "nickname": _safe_text(candidate.get("nickname")) or "Unknown",
                "matchScore": score,
                "reasons": _reasons_from_features_fallback(features),
                "debug": {
                    "rule_score": score,
                    "final_score": score,
                },
            }
        )

    results.sort(key=lambda item: (-int(item.get("matchScore") or 0), _safe_text(item.get("id"))))
    return results[:top_k]


def _profile_region_sido(profile: dict) -> str:
    return _safe_text(
        _first_non_empty(
            profile.get("regionSido"),
            _safe_dict(profile.get("performancePreferences")).get("activityRegionSido"),
        )
    )


def _profile_instruments(profile: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(_first_non_empty(profile.get("instruments"), profile.get("playableInstruments")))
        if str(item).strip()
    }


def _profile_recruiting_sessions(profile: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(_first_non_empty(profile.get("recruitingSessions"), profile.get("recruiting_sessions")))
        if str(item).strip()
    }


def _candidate_region_sido(candidate: dict) -> str:
    return _safe_text(candidate.get("regionSido"))


def _candidate_instruments(candidate: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(candidate.get("instruments"))
        if str(item).strip()
    }


def _candidate_recruiting_sessions(candidate: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(candidate.get("recruitingSessions"))
        if str(item).strip()
    }


def _passes_hard_filters(profile: dict, candidate: dict, hard_filters: dict, mode: str) -> tuple[bool, str]:
    if hard_filters.get("same_instrument"):
        if mode == "apply":
            candidate_sessions = _candidate_recruiting_sessions(candidate) or _candidate_instruments(candidate)
            overlap = _profile_instruments(profile) & candidate_sessions
        else:
            overlap = (_profile_recruiting_sessions(profile) or _profile_instruments(profile)) & _candidate_instruments(candidate)
        if not overlap:
            return False, "same_instrument_mismatch"

    if hard_filters.get("same_region"):
        user_sido = _profile_region_sido(profile)
        candidate_sido = _candidate_region_sido(candidate)
        if user_sido and candidate_sido and user_sido != candidate_sido:
            return False, "same_region_mismatch"

    return True, "passed"


def _merge_recruit_needs(profile: dict, recruit_needs: list[dict]) -> dict:
    if not recruit_needs:
        return profile
    merged = dict(profile)
    merged["recruitNeeds"] = recruit_needs
    if not merged.get("recruitingSessions"):
        merged["recruitingSessions"] = [
            need.get("instrument")
            for need in recruit_needs
            if isinstance(need, dict) and _safe_text(need.get("instrument"))
        ]
    return merged


def _candidate_to_card(candidate: dict) -> dict:
    return {
        "team_name": _safe_text(_first_non_empty(candidate.get("team_name"), candidate.get("teamName"))),
        "teamProfile": _safe_dict(candidate.get("teamProfile")),
        "leaderProfile": _safe_dict(candidate.get("leaderProfile")),
        "has_team": bool(candidate.get("has_team")),
        "team_id": _safe_text(candidate.get("team_id")),
        "instruments": _safe_list(candidate.get("instruments")),
        "parts": _safe_list(candidate.get("parts")),
        "genres": _safe_list(candidate.get("genres")),
        "style": str(candidate.get("style") or ""),
        "region": str(candidate.get("region") or ""),
        "availability": _safe_list(candidate.get("availability")),
        "practiceFrequency": str(candidate.get("practiceFrequency") or ""),
        "targetLevel": str(candidate.get("targetLevel") or ""),
        "activityGoal": str(candidate.get("activityGoal") or ""),
        "tags": _safe_list(candidate.get("tags")),
    }


def _candidate_snapshot(candidate: dict) -> dict:
    return {
        "team_name": _safe_text(_first_non_empty(candidate.get("team_name"), candidate.get("teamName"))),
        "teamProfile": _safe_dict(candidate.get("teamProfile")),
        "has_team": bool(candidate.get("has_team")),
        "team_id": _safe_text(candidate.get("team_id")),
        "instruments": _safe_list(candidate.get("instruments")),
        "parts": _safe_list(candidate.get("parts")),
        "genres": _safe_list(candidate.get("genres")),
        "style": str(candidate.get("style") or ""),
        "region": str(candidate.get("region") or ""),
        "availability": _safe_list(candidate.get("availability")),
        "practiceFrequency": str(candidate.get("practiceFrequency") or ""),
        "activityGoal": str(candidate.get("activityGoal") or ""),
    }


def _candidate_ai_summary(candidate: dict, mode: str) -> str | None:
    if mode == "apply":
        value = _safe_text(
            _first_non_empty(
                candidate.get("_recruit_summary"),
                _safe_dict(candidate.get("teamProfile")).get("ai_summary"),
            )
        )
    else:
        value = _safe_text(
            _first_non_empty(
                candidate.get("_profile_summary"),
                candidate.get("ai_summary"),
            )
        )
    return value or None


def _is_active_candidate(candidate: dict) -> bool:
    # User model currently has no explicit active flag; treat non-empty candidate payload as active.
    return bool(candidate.get("id")) and isinstance(candidate, dict)


def _is_onboarding_done_candidate(candidate: dict) -> bool:
    return bool(_safe_list(candidate.get("instruments")) or _safe_list(candidate.get("genres")))


def _is_mode_eligible_candidate(candidate: dict, mode: str) -> bool:
    if mode == "recruit":
        return bool(_safe_list(candidate.get("instruments")))
    return bool(
        _safe_list(candidate.get("recruitingSessions"))
        or _safe_list(candidate.get("recruitNeeds"))
        or _safe_list(candidate.get("instruments"))
    )


def _mode_eligibility_reason(candidate: dict, mode: str) -> str:
    if mode == "recruit":
        if not _safe_list(candidate.get("instruments")):
            return "missing_instruments_for_recruit"
        return "eligible"
    if not (
        _safe_list(candidate.get("recruitingSessions"))
        or _safe_list(candidate.get("recruitNeeds"))
        or _safe_list(candidate.get("instruments"))
    ):
        return "missing_sessions_for_apply"
    return "eligible"


def _append_reason_sample(samples: list[str], value: str, max_items: int = 5) -> None:
    if len(samples) >= max_items:
        return
    samples.append(value)


def _normalize_profile_for_engine(profile: dict, hard_filters: dict) -> dict:
    del hard_filters
    return _build_engine_payload(profile, fallback_to_instruments_for_recruiting=False)


def _normalize_candidate_for_engine(candidate: dict) -> dict:
    profile_data = _safe_dict(candidate.get("_profile_data"))
    merged = {**profile_data, **candidate}
    return _build_engine_payload(merged, fallback_to_instruments_for_recruiting=True)


def _safe_log_match_features(**kwargs: Any) -> None:
    try:
        log_match_features(**kwargs)
    except Exception:
        logger.exception(
            "match_feature_log_failed recommendation_id=%s candidate_id=%s",
            kwargs.get("recommendation_id"),
            kwargs.get("candidate_id"),
        )


def _safe_log_match_event(**kwargs: Any) -> None:
    try:
        log_match_event(**kwargs)
    except Exception:
        logger.exception(
            "match_event_log_failed recommendation_id=%s candidate_id=%s event_type=%s",
            kwargs.get("recommendation_id"),
            kwargs.get("candidate_id"),
            kwargs.get("event_type"),
        )


def list_user_candidates(db: Session, exclude_user_id: str | None = None) -> list[dict]:
    if exclude_user_id:
        base_users = chat_service.list_chat_candidates(db, exclude_user_id)
    else:
        base_users = db.scalars(select(User).order_by(User.created_at.desc())).all()

    base_ids = [user.id for user in base_users]
    if not base_ids:
        return []

    rows = db.execute(
        select(User, MatchingProfile)
        .join(MatchingProfile, MatchingProfile.user_id == User.id)
        .where(User.id.in_(base_ids))
    ).all()

    membership_rows = db.execute(
        select(TeamMember.user_id, TeamMember.team_id).where(TeamMember.user_id.in_(base_ids))
    ).all()
    team_id_by_user_id = {user_id: team_id for user_id, team_id in membership_rows}

    profile_by_user_id: dict[str, tuple[User, MatchingProfile]] = {
        user.id: (user, matching_profile)
        for user, matching_profile in rows
    }

    candidates: list[dict] = []
    for user in base_users:
        if user.id in team_id_by_user_id:
            continue

        pair = profile_by_user_id.get(user.id)
        if not pair:
            continue
        profile_user, matching_profile = pair
        candidate = {
            "id": profile_user.id,
            "nickname": profile_user.nickname,
            "has_team": False,
            "team_id": "",
            "_profile_data": matching_profile.profile_data or {},
            "_profile_summary": matching_profile.profile_summary,
            **(matching_profile.candidate_data or {}),
        }
        candidates.append(candidate)
    return candidates


def list_team_candidates(db: Session, viewer_id: str | None = None) -> list[dict]:
    base_teams = db.scalars(select(Team).order_by(Team.created_at.desc())).all()
    if not base_teams:
        return []

    viewer_team_id: int | None = None
    if viewer_id and viewer_id != "anonymous":
        viewer_team = db.scalar(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == viewer_id)
            .order_by(Team.created_at.desc())
        )
        if not viewer_team:
            viewer_team = db.scalar(select(Team).where(Team.leader_id == viewer_id).order_by(Team.created_at.desc()))
        if viewer_team:
            viewer_team_id = viewer_team.id

    team_ids = [team.id for team in base_teams if team.id != viewer_team_id]
    if not team_ids:
        return []

    team_profile_rows = db.execute(
        select(TeamMatchingProfile).where(TeamMatchingProfile.team_id.in_(team_ids))
    ).scalars().all()
    team_profile_by_team_id = {row.team_id: row for row in team_profile_rows}

    leader_ids = [team.leader_id for team in base_teams if team.id in team_ids]
    leader_profiles = db.execute(
        select(MatchingProfile).where(MatchingProfile.user_id.in_(leader_ids))
    ).scalars().all() if leader_ids else []
    leader_profile_by_user_id = {row.user_id: row for row in leader_profiles}

    candidates: list[dict] = []
    for team in base_teams:
        if team.id == viewer_team_id:
            continue

        team_matching_profile = team_profile_by_team_id.get(team.id)
        team_profile_data, recruit_needs = _team_to_profile_data(team, team_matching_profile)
        leader_matching_profile = leader_profile_by_user_id.get(team.leader_id)
        leader_profile = _build_leader_profile_data(
            leader_matching_profile.profile_data if leader_matching_profile else {},
            leader_matching_profile.candidate_data if leader_matching_profile else {},
        )
        candidate = {
            "id": str(team.id),
            "nickname": team.team_name,
            "has_team": True,
            "team_id": str(team.id),
            "team_name": team.team_name,
            "_recruit_summary": team_matching_profile.recruit_summary if team_matching_profile else None,
            "teamProfile": _safe_dict(team_profile_data.get("teamProfile")),
            "leaderProfile": leader_profile,
            "recruitNeeds": recruit_needs,
            "recruitingSessions": _safe_list(team_profile_data.get("recruitingSessions")),
            "genres": _safe_list(team_profile_data.get("genres")),
            "region": _safe_text(team_profile_data.get("region")),
            "regionSido": _safe_text(team_profile_data.get("regionSido")),
            "regionSigungu": _safe_text(team_profile_data.get("regionSigungu")),
            "practiceFrequency": _safe_text(team_profile_data.get("practiceFrequency")),
            "averageAge": _safe_text(team_profile_data.get("averageAge")),
            "activityGoal": _safe_dict(team_profile_data.get("activityGoal")),
            "_profile_data": team_profile_data,
        }
        candidates.append(candidate)
    return candidates


def list_candidates(db: Session, mode: str, viewer_id: str | None = None) -> list[dict]:
    if mode == "apply":
        return list_team_candidates(db, viewer_id=viewer_id)
    return list_user_candidates(db, exclude_user_id=viewer_id)


def recommend_matches(
    db: Session,
    profile: dict,
    mode: str = "apply",
    min_score: int = 0,
    limit: int = 10,
    recruit_needs: list[dict] | None = None,
    hard_filters: dict | None = None,
    viewer_id: str | None = None,
    ranking_version: str = DEFAULT_RANKING_VERSION,
) -> dict:
    recommendation_id = str(uuid4())
    hard_filters = hard_filters or {}
    recruit_needs = recruit_needs or []
    viewer_id = viewer_id or "anonymous"

    try:
        (
            get_top_matches,
            generate_candidates,
            normalize_profile,
            extract_apply_features,
            extract_recruit_features,
            used_fallback,
        ) = _load_band_matching()

        effective_ranking_version = ranking_version or DEFAULT_RANKING_VERSION
        if used_fallback and effective_ranking_version == DEFAULT_RANKING_VERSION:
            effective_ranking_version = FALLBACK_RANKING_VERSION

        total_users = db.scalar(select(func.count()).select_from(User)) or 0
        all_candidates = list_candidates(db, mode=mode, viewer_id=viewer_id)
        if not all_candidates:
            all_candidates = generate_candidates(n=100, seed=42)

        active_candidates = [c for c in all_candidates if _is_active_candidate(c)]
        onboarding_candidates = [c for c in active_candidates if _is_onboarding_done_candidate(c)]
        after_self_exclude = [c for c in onboarding_candidates if str(c.get("id")) != viewer_id]

        mode_eligible_candidates: list[dict] = []
        mode_eligible_excluded_samples: list[str] = []
        for candidate in after_self_exclude:
            reason = _mode_eligibility_reason(candidate, mode)
            if reason == "eligible":
                mode_eligible_candidates.append(candidate)
            else:
                _append_reason_sample(
                    mode_eligible_excluded_samples,
                    f"id={candidate.get('id')} reason={reason}",
                )

        enriched_profile, enriched_recruit_needs = _enrich_request_profile(
            db,
            profile,
            recruit_needs,
            viewer_id,
            mode,
        )
        normalized_profile = _merge_recruit_needs(enriched_profile, enriched_recruit_needs)
        engine_profile = _normalize_profile_for_engine(normalized_profile, hard_filters)

        candidate_pairs: list[tuple[dict, dict]] = []
        hard_filter_excluded_samples: list[str] = []
        for raw_candidate in mode_eligible_candidates:
            engine_candidate = _normalize_candidate_for_engine(raw_candidate)
            passed, reason = _passes_hard_filters(engine_profile, engine_candidate, hard_filters, mode)
            if passed:
                candidate_pairs.append((raw_candidate, engine_candidate))
            else:
                _append_reason_sample(
                    hard_filter_excluded_samples,
                    f"id={raw_candidate.get('id')} reason={reason}",
                )

        filtered_candidates_raw = [pair[0] for pair in candidate_pairs]
        filtered_candidates_engine = [pair[1] for pair in candidate_pairs]

        normalized_profile_for_features = normalize_profile(engine_profile)

        scored = get_top_matches(
            profile_data=engine_profile,
            candidates=filtered_candidates_engine,
            mode=mode,
            min_score=min_score,
            top_k=limit,
            viewer_id=viewer_id,
            enable_feature_logging=False,
        )
        scored_ids = {str(item.get("id")) for item in scored}
        scoring_excluded_samples: list[str] = []
        for candidate in filtered_candidates_engine:
            cid = str(candidate.get("id"))
            if cid not in scored_ids:
                _append_reason_sample(
                    scoring_excluded_samples,
                    f"id={cid} reason=engine_filtered_or_below_min_score",
                )

        candidate_map = {str(item.get("id")): item for item in filtered_candidates_raw}
        results: list[dict] = []

        for rank_position, item in enumerate(scored, start=1):
            try:
                candidate = candidate_map.get(str(item.get("id")), {})
                candidate_id = str(item.get("id") or "")
                debug = item.get("debug") or {}
                rule_score = int(debug.get("rule_score") or item.get("matchScore") or item.get("score") or 0)
                final_score = int(debug.get("final_score") or item.get("matchScore") or item.get("score") or 0)

                if mode == "recruit":
                    features = extract_recruit_features(
                        normalized_profile_for_features,
                        candidate,
                        normalized_profile_for_features.get("recruitNeeds", []),
                    )
                else:
                    features = extract_apply_features(normalized_profile_for_features, candidate)

                _safe_log_match_features(
                    recommendation_id=recommendation_id,
                    viewer_id=viewer_id,
                    candidate_id=candidate_id,
                    mode=mode,
                    rule_score=rule_score,
                    final_score=final_score,
                    rank_position=rank_position,
                    features=features,
                    candidate_snapshot=_candidate_snapshot(candidate),
                    ranking_version=effective_ranking_version,
                )

                _safe_log_match_event(
                    viewer_id=viewer_id,
                    candidate_id=candidate_id,
                    recommendation_id=recommendation_id,
                    event_type="match_shown",
                    mode=mode,
                    match_score=final_score,
                    rank_position=rank_position,
                    extra={"ranking_version": effective_ranking_version},
                )

                card_data = _candidate_to_card(candidate)
                ai_summary = _candidate_ai_summary(candidate, mode)

                results.append(
                    {
                        "recommendation_id": recommendation_id,
                        "rank_position": rank_position,
                        "id": candidate_id,
                        "nickname": str(item.get("nickname") or "Unknown"),
                        "matchScore": final_score,
                        "reasons": _safe_list(item.get("reasons")),
                        "ai_summary": ai_summary,
                        **card_data,
                    }
                )
            except Exception:
                logger.exception(
                    "matching_candidate_failed recommendation_id=%s candidate_id=%s rank_position=%s",
                    recommendation_id,
                    item.get("id"),
                    rank_position,
                )
                continue

        logger.info(
            "matching_stage_counts recommendation_id=%s data=%s",
            recommendation_id,
            json.dumps(
                {
                    "mode": mode,
                    "total_users": total_users,
                    "active_users": len(active_candidates),
                    "onboarding_ready_users": len(onboarding_candidates),
                    "mode_eligible_users": len(mode_eligible_candidates),
                    "after_block_self_exclude": len(after_self_exclude),
                    "after_hard_filters": len(filtered_candidates_engine),
                    "after_scoring": len(scored),
                    "final_results_count": len(results),
                    "min_score": min_score,
                    "hard_filters": hard_filters,
                },
                ensure_ascii=False,
            ),
        )

        logger.info(
            "matching_exclusion_samples recommendation_id=%s data=%s",
            recommendation_id,
            json.dumps(
                {
                    "mode_eligible_excluded": mode_eligible_excluded_samples,
                    "hard_filter_excluded": hard_filter_excluded_samples,
                    "scoring_excluded": scoring_excluded_samples,
                },
                ensure_ascii=False,
            ),
        )

        debug_code = None
        debug_message = None
        if (
            len(results) == 0
            and not hard_filters.get("same_instrument")
            and not hard_filters.get("same_region")
            and int(min_score or 0) <= 0
        ):
            debug_code = "candidate_pool_empty"
            debug_message = "No candidates remained after scoring with hard filters off and min_score=0."
            logger.warning(
                "matching_candidate_pool_empty recommendation_id=%s code=%s message=%s",
                recommendation_id,
                debug_code,
                debug_message,
            )

        return {
            "recommendation_id": recommendation_id,
            "ranking_version": effective_ranking_version,
            "results": results,
            "debug_code": debug_code,
            "debug_message": debug_message,
        }
    except Exception as exc:
        logger.exception(
            "matching_request_failed recommendation_id=%s mode=%s min_score=%s error_type=%s error=%s",
            recommendation_id,
            mode,
            min_score,
            type(exc).__name__,
            str(exc),
        )
        raise


def record_match_event(
    *,
    viewer_id: str,
    candidate_id: str,
    recommendation_id: str,
    event_type: str,
    mode: str,
    match_score: int | None = None,
    rank_position: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, bool]:
    _safe_log_match_event(
        viewer_id=viewer_id,
        candidate_id=candidate_id,
        recommendation_id=recommendation_id,
        event_type=event_type,
        mode=mode,
        match_score=match_score,
        rank_position=rank_position,
        extra=extra,
    )
    return {"ok": True}
