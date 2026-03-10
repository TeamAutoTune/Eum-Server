from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.matching import MatchingProfile
from app.models.user import User
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
    perf = profile.get("performancePreferences") or {}
    return str(perf.get("activityRegionSido") or "").strip()


def _profile_instruments(profile: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(profile.get("playableInstruments"))
        if str(item).strip()
    }


def _candidate_region_sido(candidate: dict) -> str:
    return str(candidate.get("regionSido") or "").strip()


def _candidate_instruments(candidate: dict) -> set[str]:
    return {
        str(item).strip()
        for item in _safe_list(candidate.get("instruments"))
        if str(item).strip()
    }


def _passes_hard_filters(profile: dict, candidate: dict, hard_filters: dict) -> bool:
    if hard_filters.get("same_instrument"):
        if not (_profile_instruments(profile) & _candidate_instruments(candidate)):
            return False

    if hard_filters.get("same_region"):
        user_sido = _profile_region_sido(profile)
        candidate_sido = _candidate_region_sido(candidate)
        if user_sido and candidate_sido and user_sido != candidate_sido:
            return False

    return True


def _merge_recruit_needs(profile: dict, recruit_needs: list[dict]) -> dict:
    if not recruit_needs:
        return profile
    merged = dict(profile)
    merged["recruitNeeds"] = recruit_needs
    return merged


def _candidate_to_card(candidate: dict) -> dict:
    return {
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
        "instruments": _safe_list(candidate.get("instruments")),
        "parts": _safe_list(candidate.get("parts")),
        "genres": _safe_list(candidate.get("genres")),
        "style": str(candidate.get("style") or ""),
        "region": str(candidate.get("region") or ""),
        "availability": _safe_list(candidate.get("availability")),
        "practiceFrequency": str(candidate.get("practiceFrequency") or ""),
        "activityGoal": str(candidate.get("activityGoal") or ""),
    }


def _is_active_candidate(candidate: dict) -> bool:
    # User model currently has no explicit active flag; treat non-empty candidate payload as active.
    return bool(candidate.get("id")) and isinstance(candidate, dict)


def _is_onboarding_done_candidate(candidate: dict) -> bool:
    return bool(_safe_list(candidate.get("instruments")) or _safe_list(candidate.get("genres")))


def _is_mode_eligible_candidate(candidate: dict, mode: str) -> bool:
    if mode == "recruit":
        return bool(_safe_list(candidate.get("instruments")) and _safe_list(candidate.get("parts")))
    return bool(_safe_list(candidate.get("instruments")))


def _normalize_profile_for_engine(profile: dict, hard_filters: dict) -> dict:
    perf = dict(profile.get("performancePreferences") or {})
    goal = dict(profile.get("activityGoal") or {})
    match_conditions = dict(profile.get("matchConditions") or {})

    normalized = dict(profile)
    normalized["playableInstruments"] = [_norm_text(v) for v in _safe_list(profile.get("playableInstruments")) if _norm_text(v)]
    normalized["primaryParts"] = [_norm_text(v) for v in _safe_list(profile.get("primaryParts")) if _norm_text(v)]
    normalized["preferredGenres"] = [_norm_text(v) for v in _safe_list(profile.get("preferredGenres")) if _norm_text(v)]

    perf["performanceStyle"] = _norm_text(perf.get("performanceStyle"))
    perf["activityRegion"] = _safe_text(perf.get("activityRegion"))
    perf["activityRegionSido"] = _norm_text(perf.get("activityRegionSido"))
    perf["activityRegionSigungu"] = _norm_text(perf.get("activityRegionSigungu"))
    perf["availableTimeSlots"] = [_norm_text(v) for v in _safe_list(perf.get("availableTimeSlots")) if _norm_text(v)]
    perf["practiceFrequency"] = _norm_text(perf.get("practiceFrequency"))

    if not hard_filters.get("same_region"):
        perf["activityRegionSido"] = ""
        perf["activityRegionSigungu"] = ""

    goal["activityGoals"] = [_norm_text(v) for v in _safe_list(goal.get("activityGoals")) if _norm_text(v)]
    match_conditions["requiredConditions"] = [_norm_text(v) for v in _safe_list(match_conditions.get("requiredConditions")) if _norm_text(v)]
    match_conditions["avoidConditions"] = [_norm_text(v) for v in _safe_list(match_conditions.get("avoidConditions")) if _norm_text(v)]

    normalized["performancePreferences"] = perf
    normalized["activityGoal"] = goal
    normalized["matchConditions"] = match_conditions

    normalized_needs: list[dict] = []
    for need in _safe_list(profile.get("recruitNeeds")):
        if not isinstance(need, dict):
            continue
        normalized_needs.append(
            {
                **need,
                "instrument": _norm_text(need.get("instrument")),
                "part": _norm_text(need.get("part")),
            }
        )
    normalized["recruitNeeds"] = normalized_needs
    return normalized


def _normalize_candidate_for_engine(candidate: dict) -> dict:
    normalized = dict(candidate)
    normalized["instruments"] = [_norm_text(v) for v in _safe_list(candidate.get("instruments")) if _norm_text(v)]
    normalized["parts"] = [_norm_text(v) for v in _safe_list(candidate.get("parts")) if _norm_text(v)]
    normalized["genres"] = [_norm_text(v) for v in _safe_list(candidate.get("genres")) if _norm_text(v)]
    normalized["style"] = _norm_text(candidate.get("style"))
    normalized["regionSido"] = _norm_text(candidate.get("regionSido"))
    normalized["regionSigungu"] = _norm_text(candidate.get("regionSigungu"))
    normalized["availability"] = [_norm_text(v) for v in _safe_list(candidate.get("availability")) if _norm_text(v)]
    normalized["practiceFrequency"] = _norm_text(candidate.get("practiceFrequency"))
    normalized["activityGoal"] = _norm_text(candidate.get("activityGoal"))
    normalized["tags"] = [_norm_text(v) for v in _safe_list(candidate.get("tags")) if _norm_text(v)]
    return normalized


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


def list_candidates(db: Session, exclude_user_id: str | None = None) -> list[dict]:
    rows = db.execute(
        select(User, MatchingProfile).join(MatchingProfile, MatchingProfile.user_id == User.id)
    ).all()

    candidates: list[dict] = []
    for user, matching_profile in rows:
        if exclude_user_id and user.id == exclude_user_id:
            continue

        candidate = {
            "id": user.id,
            "nickname": user.nickname,
            **(matching_profile.candidate_data or {}),
        }
        candidates.append(candidate)

    return candidates


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
    # Test mode: force disable hard filters regardless of request payload.
    hard_filters = {"same_instrument": False, "same_region": False}
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

        raw_candidates = list_candidates(db, exclude_user_id=viewer_id)
        if not raw_candidates:
            raw_candidates = generate_candidates(n=100, seed=42)

        total_count = len(raw_candidates)
        active_candidates = [c for c in raw_candidates if _is_active_candidate(c)]
        active_count = len(active_candidates)
        onboarding_candidates = [c for c in active_candidates if _is_onboarding_done_candidate(c)]
        onboarding_done_count = len(onboarding_candidates)
        mode_eligible_candidates = [
            c for c in onboarding_candidates if _is_mode_eligible_candidate(c, mode)
        ]
        mode_eligible_count = len(mode_eligible_candidates)

        normalized_profile = _merge_recruit_needs(profile, recruit_needs)
        engine_profile = _normalize_profile_for_engine(normalized_profile, hard_filters)

        candidate_pairs: list[tuple[dict, dict]] = []
        for raw_candidate in mode_eligible_candidates:
            engine_candidate = _normalize_candidate_for_engine(raw_candidate)
            if _passes_hard_filters(engine_profile, engine_candidate, hard_filters):
                candidate_pairs.append((raw_candidate, engine_candidate))

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

                results.append(
                    {
                        "recommendation_id": recommendation_id,
                        "rank_position": rank_position,
                        "id": candidate_id,
                        "nickname": str(item.get("nickname") or "Unknown"),
                        "matchScore": final_score,
                        "reasons": _safe_list(item.get("reasons")),
                        **_candidate_to_card(candidate),
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
            "matching_request recommendation_id=%s mode=%s min_score=%s total=%s active=%s onboarding_done=%s mode_eligible=%s final=%s",
            recommendation_id,
            mode,
            min_score,
            total_count,
            active_count,
            onboarding_done_count,
            mode_eligible_count,
            len(results),
        )

        return {
            "recommendation_id": recommendation_id,
            "ranking_version": effective_ranking_version,
            "results": results,
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
