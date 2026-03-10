from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.matching import MatchingProfile
from app.models.user import User
from app.services.recommendation_logging import log_match_event, log_match_features


_BAND_MATCHING_PATH = Path(__file__).resolve().parents[3] / "band_matching"
DEFAULT_RANKING_VERSION = "hybrid_v1"


def _load_band_matching() -> tuple[Any, Any, Any, Any, Any]:
    if str(_BAND_MATCHING_PATH) not in sys.path:
        sys.path.insert(0, str(_BAND_MATCHING_PATH))

    from match_engine import _extract_apply_features  # type: ignore
    from match_engine import _extract_recruit_features  # type: ignore
    from match_engine import get_top_matches  # type: ignore
    from match_engine import normalize_profile  # type: ignore
    from synthetic_data import generate_candidates  # type: ignore

    return (
        get_top_matches,
        generate_candidates,
        normalize_profile,
        _extract_apply_features,
        _extract_recruit_features,
    )


def _safe_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


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
    (
        get_top_matches,
        generate_candidates,
        normalize_profile,
        extract_apply_features,
        extract_recruit_features,
    ) = _load_band_matching()

    hard_filters = hard_filters or {}
    recruit_needs = recruit_needs or []
    viewer_id = viewer_id or "anonymous"
    recommendation_id = str(uuid4())

    candidates = list_candidates(db, exclude_user_id=viewer_id)
    if not candidates:
        candidates = generate_candidates(n=100, seed=42)

    filtered_candidates = [
        candidate
        for candidate in candidates
        if _passes_hard_filters(profile, candidate, hard_filters)
    ]

    normalized_profile = _merge_recruit_needs(profile, recruit_needs)
    normalized_profile_for_features = normalize_profile(normalized_profile)

    scored = get_top_matches(
        profile_data=normalized_profile,
        candidates=filtered_candidates,
        mode=mode,
        min_score=min_score,
        top_k=limit,
        viewer_id=viewer_id,
        enable_feature_logging=False,
    )

    candidate_map = {str(item.get("id")): item for item in filtered_candidates}
    results: list[dict] = []
    for rank_position, item in enumerate(scored, start=1):
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

        log_match_features(
            recommendation_id=recommendation_id,
            viewer_id=viewer_id,
            candidate_id=candidate_id,
            mode=mode,
            rule_score=rule_score,
            final_score=final_score,
            rank_position=rank_position,
            features=features,
            candidate_snapshot=_candidate_snapshot(candidate),
            ranking_version=ranking_version,
        )

        log_match_event(
            viewer_id=viewer_id,
            candidate_id=candidate_id,
            recommendation_id=recommendation_id,
            event_type="match_shown",
            mode=mode,
            match_score=final_score,
            rank_position=rank_position,
            extra={"ranking_version": ranking_version},
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

    return {
        "recommendation_id": recommendation_id,
        "ranking_version": ranking_version,
        "results": results,
    }


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
    log_match_event(
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
