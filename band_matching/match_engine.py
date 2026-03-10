# -*- coding: utf-8 -*-
"""Explainable rule-based match engine for band member matching."""

from __future__ import annotations

from feature_logger import log_match_features

from typing import Any, Dict, Iterable, List, Tuple

from hybrid_ranker import load_model, hybrid_score

MODEL = load_model()

CONFIG = {
    "score_range": {"min": 0, "max": 100},
    "apply_weights": {
        "genre_overlap": 20,
        "part_overlap": 10,
        "style_match": 8,
        "time_overlap": 10,
        "practice_frequency": 6,
        "activity_goal": 6,
        "required_bonus": 8,
        "avoid_penalty": 20,
        "same_sigungu_bonus": 6,
    },
    "recruit_weights": {
        "recruit_needs_coverage": 40,
        "genre_overlap": 14,
        "part_overlap": 8,
        "style_match": 6,
        "time_overlap": 8,
        "practice_frequency": 6,
        "activity_goal": 6,
        "required_bonus": 6,
        "avoid_penalty": 16,
        "same_sigungu_bonus": 6,
    },
    "practice_frequency_matrix": {
        "weekly_1": {"weekly_1": 1.0, "weekly_2": 0.7, "weekly_3_plus": 0.4},
        "weekly_2": {"weekly_1": 0.7, "weekly_2": 1.0, "weekly_3_plus": 0.75},
        "weekly_3_plus": {"weekly_1": 0.4, "weekly_2": 0.75, "weekly_3_plus": 1.0},
    },
    "goal_similarity": {
        "hobby": {"hobby": 1.0, "busking": 0.5, "band": 0.5, "pro": 0.2},
        "busking": {"hobby": 0.5, "busking": 1.0, "band": 0.7, "pro": 0.4},
        "band": {"hobby": 0.5, "busking": 0.7, "band": 1.0, "pro": 0.6},
        "pro": {"hobby": 0.2, "busking": 0.4, "band": 0.6, "pro": 1.0},
    },
    "required_missing_penalty_apply": 12,
}

VALID_MODES = {"apply", "recruit"}


def _ensure_dict(value: Any, field_name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    return value


def _safe_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value not in (None, "") else []


def _normalize_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _unique_preserve(items: Iterable[Any]) -> list:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _setify(items: Any) -> set[str]:
    return {
        _normalize_text(item)
        for item in _safe_list(items)
        if _normalize_text(item)
    }


def _clamp_score(value: float) -> int:
    return max(CONFIG["score_range"]["min"], min(CONFIG["score_range"]["max"], int(round(value))))


def _overlap_ratio(left: Iterable[str], right: Iterable[str]) -> float:
    set_left = _setify(list(left))
    set_right = _setify(list(right))
    if not set_left or not set_right:
        return 0.0
    overlap = len(set_left & set_right)
    base = max(len(set_left), len(set_right))
    return overlap / base if base else 0.0


def _practice_similarity(profile_freq: str, candidate_freq: str) -> float:
    return CONFIG["practice_frequency_matrix"].get(profile_freq, {}).get(candidate_freq, 0.0)


def _goal_similarity(profile_goals: Iterable[str], candidate_goal: str) -> float:
    candidate_goal = _normalize_text(candidate_goal)
    goals = _setify(list(profile_goals))
    if not goals or not candidate_goal:
        return 0.0
    return max(
        CONFIG["goal_similarity"].get(goal, {}).get(candidate_goal, 0.0)
        for goal in goals
    )


def _resolve_region(profile: dict) -> str:
    region = _normalize_text(profile["performancePreferences"].get("activityRegion"))
    if region:
        return " ".join(region.split())
    sido = _normalize_text(profile["performancePreferences"].get("activityRegionSido"))
    sigungu = _normalize_text(profile["performancePreferences"].get("activityRegionSigungu"))
    return " ".join(f"{sido} {sigungu}".strip().split())


def _extract_profile_region_sido(profile: dict) -> str:
    sido = _normalize_text(profile["performancePreferences"].get("activityRegionSido"))
    if sido:
        return sido
    full_region = _resolve_region(profile)
    if not full_region:
        return ""
    return full_region.split()[0]


def _extract_profile_region_sigungu(profile: dict) -> str:
    sigungu = _normalize_text(profile["performancePreferences"].get("activityRegionSigungu"))
    if sigungu:
        return sigungu
    full_region = _resolve_region(profile)
    parts = full_region.split()
    return parts[1] if len(parts) >= 2 else ""


def _build_required_avoid_sets(profile: dict) -> tuple[set[str], set[str]]:
    raw_required = _setify(profile["matchConditions"].get("requiredConditions"))
    raw_avoid = _setify(profile["matchConditions"].get("avoidConditions"))
    return raw_required, raw_avoid - raw_required


def _get_same_sigungu_bonus(profile: dict, candidate: dict, bonus: int) -> tuple[float, str]:
    profile_sigungu = _extract_profile_region_sigungu(profile)
    candidate_sigungu = _normalize_text(candidate.get("regionSigungu"))
    if profile_sigungu and candidate_sigungu and profile_sigungu == candidate_sigungu:
        return float(bonus), f"같은 시군구 활동권 / Same district: {profile_sigungu}"
    return 0.0, ""


def normalize_profile(profile_data: dict) -> dict:
    """Normalize raw profile data into stable internal structure."""
    if not isinstance(profile_data, dict):
        raise ValueError("profile_data must be a dict")

    performance_preferences = _ensure_dict(
        profile_data.get("performancePreferences"),
        "performancePreferences",
    )
    activity_goal = _ensure_dict(profile_data.get("activityGoal"), "activityGoal")
    match_conditions = _ensure_dict(profile_data.get("matchConditions"), "matchConditions")

    recruit_needs_raw = _safe_list(profile_data.get("recruitNeeds"))
    recruit_needs: list[dict] = []
    for item in recruit_needs_raw:
        if not isinstance(item, dict):
            continue
        recruit_needs.append(
            {
                "instrument": _normalize_text(item.get("instrument")),
                "part": _normalize_text(item.get("part")),
                "count": int(item.get("count", 1) or 1),
                "required": bool(item.get("required", False)),
            }
        )

    return {
        "playableInstruments": _unique_preserve(
            [_normalize_text(x) for x in _safe_list(profile_data.get("playableInstruments")) if _normalize_text(x)]
        ),
        "primaryParts": _unique_preserve(
            [_normalize_text(x) for x in _safe_list(profile_data.get("primaryParts")) if _normalize_text(x)]
        ),
        "preferredGenres": _unique_preserve(
            [_normalize_text(x) for x in _safe_list(profile_data.get("preferredGenres")) if _normalize_text(x)]
        ),
        "lifeSongs": _unique_preserve(
            [_normalize_text(x) for x in _safe_list(profile_data.get("lifeSongs")) if _normalize_text(x)]
        ),
        "favoriteArtists": _unique_preserve(
            [_normalize_text(x) for x in _safe_list(profile_data.get("favoriteArtists")) if _normalize_text(x)]
        ),
        "performancePreferences": {
            "performanceStyle": _normalize_text(performance_preferences.get("performanceStyle")),
            "activityRegion": _normalize_text(performance_preferences.get("activityRegion")),
            "activityRegionSido": _normalize_text(performance_preferences.get("activityRegionSido")),
            "activityRegionSigungu": _normalize_text(performance_preferences.get("activityRegionSigungu")),
            "availableTimeSlots": _unique_preserve(
                [_normalize_text(x) for x in _safe_list(performance_preferences.get("availableTimeSlots")) if _normalize_text(x)]
            ),
            "practiceFrequency": _normalize_text(performance_preferences.get("practiceFrequency")),
        },
        "activityGoal": {
            "activityGoals": _unique_preserve(
                [_normalize_text(x) for x in _safe_list(activity_goal.get("activityGoals")) if _normalize_text(x)]
            )
        },
        "matchConditions": {
            "requiredConditions": _unique_preserve(
                [_normalize_text(x) for x in _safe_list(match_conditions.get("requiredConditions")) if _normalize_text(x)]
            ),
            "avoidConditions": _unique_preserve(
                [_normalize_text(x) for x in _safe_list(match_conditions.get("avoidConditions")) if _normalize_text(x)]
            ),
        },
        "recruitNeeds": recruit_needs,
    }


def hard_filter(profile: dict, candidate: dict) -> Tuple[bool, str]:
    """Apply hard filters: instrument overlap + regionSido exact match."""
    profile_instruments = _setify(profile.get("playableInstruments"))
    candidate_instruments = _setify(candidate.get("instruments"))
    if not (profile_instruments & candidate_instruments):
        return False, "악기 하드필터 불일치"

    profile_sido = _extract_profile_region_sido(profile)
    candidate_sido = _normalize_text(candidate.get("regionSido"))
    if profile_sido and candidate_sido and profile_sido != candidate_sido:
        return False, "활동지역(시/도) 하드필터 불일치"

    return True, "통과"


def _required_and_avoid_adjustment(
    required_conditions: set[str],
    avoid_conditions: set[str],
    candidate_tags: set[str],
    max_required_bonus: int,
    max_avoid_penalty: int,
    reasons: list[str],
) -> tuple[float, float]:
    required_bonus = 0.0
    avoid_penalty = 0.0

    if required_conditions:
        matched_required = required_conditions & candidate_tags
        ratio = len(matched_required) / len(required_conditions)
        required_bonus = ratio * max_required_bonus
        if matched_required:
            reasons.append(
                f"필수 조건 일부 충족 / Required matched: {', '.join(sorted(matched_required))}"
            )

    if avoid_conditions:
        conflicts = avoid_conditions & candidate_tags
        if conflicts:
            ratio = len(conflicts) / len(avoid_conditions)
            avoid_penalty = ratio * max_avoid_penalty
            reasons.append(
                f"비선호 조건 충돌 / Avoid conflicts: {', '.join(sorted(conflicts))}"
            )

    return required_bonus, avoid_penalty


def score_apply_mode(profile: dict, candidate: dict) -> dict:
    """Score candidate for apply mode."""
    weights = CONFIG["apply_weights"]
    reasons: list[str] = []
    debug: dict[str, float] = {}

    genre_ratio = _overlap_ratio(profile["preferredGenres"], candidate.get("genres"))
    genre_score = genre_ratio * weights["genre_overlap"]
    debug["genre_overlap"] = genre_score
    if genre_ratio > 0:
        shared = sorted(_setify(profile["preferredGenres"]) & _setify(candidate.get("genres")))
        reasons.append(f"선호 장르 겹침 / Shared genres: {', '.join(shared)}")

    part_ratio = _overlap_ratio(profile["primaryParts"], candidate.get("parts"))
    part_score = part_ratio * weights["part_overlap"]
    debug["part_overlap"] = part_score
    if part_ratio > 0:
        shared = sorted(_setify(profile["primaryParts"]) & _setify(candidate.get("parts")))
        reasons.append(f"주요 파트 연관 / Shared parts: {', '.join(shared)}")

    style = profile["performancePreferences"]["performanceStyle"]
    style_score = weights["style_match"] if style and style == _normalize_text(candidate.get("style")) else 0.0
    debug["style_match"] = style_score
    if style_score > 0:
        reasons.append(f"연주 성향 일치 / Same style: {style}")

    time_ratio = _overlap_ratio(
        profile["performancePreferences"]["availableTimeSlots"],
        candidate.get("availability"),
    )
    time_score = time_ratio * weights["time_overlap"]
    debug["time_overlap"] = time_score
    if time_ratio > 0:
        shared = sorted(
            _setify(profile["performancePreferences"]["availableTimeSlots"])
            & _setify(candidate.get("availability"))
        )
        reasons.append(f"합주 시간대 겹침 / Shared slots: {', '.join(shared)}")

    practice_ratio = _practice_similarity(
        profile["performancePreferences"]["practiceFrequency"],
        _normalize_text(candidate.get("practiceFrequency")),
    )
    practice_score = practice_ratio * weights["practice_frequency"]
    debug["practice_frequency"] = practice_score
    if practice_ratio > 0:
        reasons.append("연습 빈도 궁합 양호 / Practice frequency compatible")

    goal_ratio = _goal_similarity(
        profile["activityGoal"]["activityGoals"],
        _normalize_text(candidate.get("activityGoal")),
    )
    goal_score = goal_ratio * weights["activity_goal"]
    debug["activity_goal"] = goal_score
    if goal_ratio > 0:
        reasons.append("활동 목표 궁합 / Activity goal aligned")

    same_sigungu_bonus, sigungu_reason = _get_same_sigungu_bonus(
        profile, candidate, weights["same_sigungu_bonus"]
    )
    debug["same_sigungu_bonus"] = same_sigungu_bonus
    if same_sigungu_bonus > 0:
        reasons.append(sigungu_reason)

    required_conditions, avoid_conditions = _build_required_avoid_sets(profile)
    candidate_tags = _setify(candidate.get("tags"))

    required_bonus, avoid_penalty = _required_and_avoid_adjustment(
        required_conditions=required_conditions,
        avoid_conditions=avoid_conditions,
        candidate_tags=candidate_tags,
        max_required_bonus=weights["required_bonus"],
        max_avoid_penalty=weights["avoid_penalty"],
        reasons=reasons,
    )
    debug["required_bonus"] = required_bonus
    debug["avoid_penalty"] = -avoid_penalty

    missing_required = required_conditions - candidate_tags
    if missing_required:
        missing_penalty = CONFIG["required_missing_penalty_apply"]
        reasons.append(
            f"필수 조건 일부 미충족 / Missing required: {', '.join(sorted(missing_required))}"
        )
    else:
        missing_penalty = 0.0
    debug["required_missing_penalty"] = -missing_penalty

    raw_score = (
        genre_score
        + part_score
        + style_score
        + time_score
        + practice_score
        + goal_score
        + same_sigungu_bonus
        + required_bonus
        - avoid_penalty
        - missing_penalty
    )

    return {
        "score": _clamp_score(raw_score),
        "reasons": reasons,
        "debug": debug,
    }


def _coverage_for_need(need: dict, candidate: dict) -> float:
    instrument = _normalize_text(need.get("instrument"))
    part = _normalize_text(need.get("part"))

    candidate_instruments = _setify(candidate.get("instruments"))
    candidate_parts = _setify(candidate.get("parts"))

    if instrument and instrument not in candidate_instruments:
        return 0.0

    if part:
        return 1.0 if part in candidate_parts else 0.0

    return 1.0 if instrument else 0.0


def score_recruit_mode(profile: dict, candidate: dict, recruit_needs: list[dict]) -> dict:
    """Score candidate for recruit mode."""
    weights = CONFIG["recruit_weights"]
    reasons: list[str] = []
    debug: dict[str, float] = {}

    normalized_needs = [need for need in recruit_needs if isinstance(need, dict)]
    required_needs = [need for need in normalized_needs if bool(need.get("required"))]

    for need in required_needs:
        if _coverage_for_need(need, candidate) <= 0:
            return {
                "score": 0,
                "reasons": [
                    f"필수 구인 조건 미충족 / Missing required recruit need: {need.get('instrument')} {need.get('part', '')}".strip()
                ],
                "debug": {"recruit_needs_coverage": 0.0},
                "excluded": True,
            }

    if normalized_needs:
        coverage_ratio = sum(_coverage_for_need(need, candidate) for need in normalized_needs) / len(normalized_needs)
    else:
        coverage_ratio = 0.0

    recruit_score = coverage_ratio * weights["recruit_needs_coverage"]
    debug["recruit_needs_coverage"] = recruit_score
    if coverage_ratio > 0:
        reasons.append("구인 니즈 충족도 높음 / Strong recruit-needs coverage")

    genre_ratio = _overlap_ratio(profile["preferredGenres"], candidate.get("genres"))
    genre_score = genre_ratio * weights["genre_overlap"]
    debug["genre_overlap"] = genre_score
    if genre_ratio > 0:
        shared = sorted(_setify(profile["preferredGenres"]) & _setify(candidate.get("genres")))
        reasons.append(f"장르 궁합 / Shared genres: {', '.join(shared)}")

    recruit_parts = [need.get("part", "") for need in normalized_needs if need.get("part")]
    part_ratio = _overlap_ratio(recruit_parts, candidate.get("parts"))
    part_score = part_ratio * weights["part_overlap"]
    debug["part_overlap"] = part_score
    if part_ratio > 0:
        shared = sorted(_setify(recruit_parts) & _setify(candidate.get("parts")))
        reasons.append(f"구인 파트 부합 / Matching recruit parts: {', '.join(shared)}")

    style = profile["performancePreferences"]["performanceStyle"]
    style_score = weights["style_match"] if style and style == _normalize_text(candidate.get("style")) else 0.0
    debug["style_match"] = style_score
    if style_score > 0:
        reasons.append(f"연주 성향 일치 / Same style: {style}")

    time_ratio = _overlap_ratio(
        profile["performancePreferences"]["availableTimeSlots"],
        candidate.get("availability"),
    )
    time_score = time_ratio * weights["time_overlap"]
    debug["time_overlap"] = time_score
    if time_ratio > 0:
        shared = sorted(
            _setify(profile["performancePreferences"]["availableTimeSlots"])
            & _setify(candidate.get("availability"))
        )
        reasons.append(f"가능 시간대 겹침 / Shared slots: {', '.join(shared)}")

    practice_ratio = _practice_similarity(
        profile["performancePreferences"]["practiceFrequency"],
        _normalize_text(candidate.get("practiceFrequency")),
    )
    practice_score = practice_ratio * weights["practice_frequency"]
    debug["practice_frequency"] = practice_score
    if practice_ratio > 0:
        reasons.append("연습 빈도 부합 / Practice frequency compatible")

    goal_ratio = _goal_similarity(
        profile["activityGoal"]["activityGoals"],
        _normalize_text(candidate.get("activityGoal")),
    )
    goal_score = goal_ratio * weights["activity_goal"]
    debug["activity_goal"] = goal_score
    if goal_ratio > 0:
        reasons.append("활동 목표 부합 / Activity goal aligned")

    same_sigungu_bonus, sigungu_reason = _get_same_sigungu_bonus(
        profile, candidate, weights["same_sigungu_bonus"]
    )
    debug["same_sigungu_bonus"] = same_sigungu_bonus
    if same_sigungu_bonus > 0:
        reasons.append(sigungu_reason)

    required_conditions, avoid_conditions = _build_required_avoid_sets(profile)
    candidate_tags = _setify(candidate.get("tags"))
    required_bonus, avoid_penalty = _required_and_avoid_adjustment(
        required_conditions=required_conditions,
        avoid_conditions=avoid_conditions,
        candidate_tags=candidate_tags,
        max_required_bonus=weights["required_bonus"],
        max_avoid_penalty=weights["avoid_penalty"],
        reasons=reasons,
    )
    debug["required_bonus"] = required_bonus
    debug["avoid_penalty"] = -avoid_penalty

    raw_score = (
        recruit_score
        + genre_score
        + part_score
        + style_score
        + time_score
        + practice_score
        + goal_score
        + same_sigungu_bonus
        + required_bonus
        - avoid_penalty
    )

    return {
        "score": _clamp_score(raw_score),
        "reasons": reasons,
        "debug": debug,
        "excluded": False,
    }


def get_top_matches(
    profile_data: dict,
    candidates: list[dict],
    mode: str = "apply",
    min_score: int = 0,
    top_k: int = 20,
    viewer_id: str = "anonymous",
    enable_feature_logging: bool = False,
) -> list[dict]:
    """Return ranked match results."""
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    if min_score < 0:
        raise ValueError("min_score must be >= 0")
    if top_k < 0:
        raise ValueError("top_k must be >= 0")

    profile = normalize_profile(profile_data)
    results: list[dict] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        passed, _ = hard_filter(profile, candidate)
        if not passed:
            continue

        if mode == "apply":
          scored = score_apply_mode(profile, candidate)
          if enable_feature_logging:
              features = _extract_apply_features(profile, candidate)
          else:
              features = _extract_apply_features(profile, candidate)

        else:
            scored = score_recruit_mode(profile, candidate, profile.get("recruitNeeds", []))
            if scored.get("excluded"):
                continue
            if enable_feature_logging:
                features = _extract_recruit_features(
                    profile,
                    candidate,
                    profile.get("recruitNeeds", []),
                )
            else:
                features = _extract_recruit_features(
                    profile,
                    candidate,
                    profile.get("recruitNeeds", []),
                )

        rule_score = _clamp_score(scored.get("score", 0))

        final_score = hybrid_score(
            rule_score=rule_score,
            features=features,
            model=MODEL,
        )

        score = _clamp_score(final_score)

        if score < min_score:
            continue

        reasons = list(scored.get("reasons", [])) or ["기본 조건 일치 / Basic requirements matched"]

        if enable_feature_logging:
            if mode == "apply":
                features = _extract_apply_features(profile, candidate)
            else:
                features = _extract_recruit_features(
                    profile,
                    candidate,
                    profile.get("recruitNeeds", []),
                )

            log_match_features(
                viewer_id=viewer_id,
                candidate_id=_normalize_text(candidate.get("id")),
                mode=mode,
                features=features,
                rule_score=score,
                extra={
                    "nickname": _normalize_text(candidate.get("nickname")) or "Unknown","final_score": score,
                },
            )        
        debug = dict(scored.get("debug", {}))
        debug["rule_score"] = rule_score
        debug["final_score"] = score
        results.append(
            {
                "id": _normalize_text(candidate.get("id")),
                "nickname": _normalize_text(candidate.get("nickname")) or "Unknown",
                "matchScore": score,
                "reasons": reasons,
                "debug": debug,
            }
        )

    results.sort(key=lambda item: (-item["matchScore"], item["id"]))
    return results[:top_k]

def _safe_ratio(numerator: int, denominator: int) -> float:
    """Return safe ratio."""
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _extract_apply_features(profile: dict, candidate: dict) -> dict:
    """Extract structured features for apply mode logging."""
    profile_genres = _setify(profile.get("preferredGenres"))
    candidate_genres = _setify(candidate.get("genres"))
    shared_genres = profile_genres & candidate_genres

    profile_parts = _setify(profile.get("primaryParts"))
    candidate_parts = _setify(candidate.get("parts"))
    shared_parts = profile_parts & candidate_parts

    profile_slots = _setify(profile["performancePreferences"].get("availableTimeSlots"))
    candidate_slots = _setify(candidate.get("availability"))
    shared_slots = profile_slots & candidate_slots

    profile_style = _normalize_text(profile["performancePreferences"].get("performanceStyle"))
    candidate_style = _normalize_text(candidate.get("style"))

    profile_freq = _normalize_text(profile["performancePreferences"].get("practiceFrequency"))
    candidate_freq = _normalize_text(candidate.get("practiceFrequency"))

    profile_goals = _setify(profile["activityGoal"].get("activityGoals"))
    candidate_goal = _normalize_text(candidate.get("activityGoal"))

    required_conditions, avoid_conditions = _build_required_avoid_sets(profile)
    candidate_tags = _setify(candidate.get("tags"))

    required_matched = required_conditions & candidate_tags
    avoid_conflicts = avoid_conditions & candidate_tags

    profile_sido = _extract_profile_region_sido(profile)
    profile_sigungu = _extract_profile_region_sigungu(profile)

    candidate_sido = _normalize_text(candidate.get("regionSido"))
    candidate_sigungu = _normalize_text(candidate.get("regionSigungu"))

    return {
        "instrument_overlap": 1.0 if (_setify(profile.get("playableInstruments")) & _setify(candidate.get("instruments"))) else 0.0,
        "region_sido_match": 1.0 if profile_sido and candidate_sido and profile_sido == candidate_sido else 0.0,
        "same_sigungu": 1.0 if profile_sigungu and candidate_sigungu and profile_sigungu == candidate_sigungu else 0.0,
        "genre_overlap_ratio": _safe_ratio(len(shared_genres), max(len(profile_genres), len(candidate_genres))),
        "part_overlap_ratio": _safe_ratio(len(shared_parts), max(len(profile_parts), len(candidate_parts))),
        "style_match": 1.0 if profile_style and profile_style == candidate_style else 0.0,
        "time_overlap_ratio": _safe_ratio(len(shared_slots), max(len(profile_slots), len(candidate_slots))),
        "practice_similarity": _practice_similarity(profile_freq, candidate_freq),
        "goal_similarity": _goal_similarity(profile_goals, candidate_goal),
        "required_match_ratio": _safe_ratio(len(required_matched), len(required_conditions)),
        "avoid_conflict_ratio": _safe_ratio(len(avoid_conflicts), len(avoid_conditions)),
    }  
    
def _extract_recruit_features(profile: dict, candidate: dict, recruit_needs: list[dict]) -> dict:
    """Extract structured features for recruit mode logging."""
    base = _extract_apply_features(profile, candidate)

    normalized_needs = [need for need in recruit_needs if isinstance(need, dict)]
    if normalized_needs:
        coverage_values = [_coverage_for_need(need, candidate) for need in normalized_needs]
        required_needs = [need for need in normalized_needs if bool(need.get("required"))]
        required_coverage_values = [_coverage_for_need(need, candidate) for need in required_needs]
    else:
        coverage_values = []
        required_needs = []
        required_coverage_values = []

    base.update(
        {
            "recruit_needs_coverage": (
                sum(coverage_values) / len(coverage_values) if coverage_values else 0.0
            ),
            "required_recruit_needs_coverage": (
                sum(required_coverage_values) / len(required_coverage_values)
                if required_coverage_values
                else 0.0
            ),
            "required_recruit_need_count": float(len(required_needs)),
            "recruit_need_count": float(len(normalized_needs)),
        }
    )
    return base