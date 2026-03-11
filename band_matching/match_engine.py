"""Rule-based matching engine for band/team matching.

This module is intentionally self-contained so it can replace the legacy
`band_matching` folder with minimal integration changes.
"""

from __future__ import annotations

from typing import Any, Iterable

VALID_MODES = {"apply", "recruit"}

WEIGHTS = {
    "genre_overlap": 25,
    "goal_match": 20,
    "practice_similarity": 15,
    "style_similarity": 15,
    "age_similarity": 10,
    "lifestyle_similarity": 10,
    "region_match": 5,
}

REASON_LABELS = {
    "session_match": "모집 세션이 맞아요",
    "genre_overlap": "선호 장르가 잘 맞아요",
    "goal_match": "활동 목표가 비슷해요",
    "practice_similarity": "연습 빈도가 잘 맞아요",
    "style_similarity": "연주 스타일이 잘 맞아요",
    "age_similarity": "연령대 분위기가 비슷해요",
    "lifestyle_similarity": "생활 스타일이 잘 맞아요",
    "region_match": "활동 지역이 같아요",
}

INSTRUMENT_CODE_MAP = {
    "vocal": "VOCAL",
    "보컬": "VOCAL",
    "guitar": "GUITAR",
    "기타": "GUITAR",
    "bass": "BASS",
    "베이스": "BASS",
    "drum": "DRUM",
    "drums": "DRUM",
    "드럼": "DRUM",
    "keyboard": "KEYBOARD",
    "키보드": "KEYBOARD",
    "piano": "PIANO",
    "피아노": "PIANO",
    "violin": "VIOLIN",
    "바이올린": "VIOLIN",
    "saxophone": "SAXOPHONE",
    "색소폰": "SAXOPHONE",
    "trumpet": "TRUMPET",
    "트럼펫": "TRUMPET",
    "dj": "DJ",
}

GENRE_CODE_MAP = {
    "rock": "ROCK",
    "록": "ROCK",
    "indie": "INDIE",
    "인디": "INDIE",
    "ballad": "BALLAD",
    "발라드": "BALLAD",
    "jazz": "JAZZ",
    "재즈": "JAZZ",
    "r&b": "RNB",
    "rnb": "RNB",
    "알앤비": "RNB",
    "metal": "METAL",
    "메탈": "METAL",
    "pop": "POP",
    "팝": "POP",
    "hip-hop": "HIPHOP",
    "hiphop": "HIPHOP",
    "힙합": "HIPHOP",
    "funk": "FUNK",
    "펑크": "FUNK",
    "electronic": "ELECTRONIC",
    "일렉트로닉": "ELECTRONIC",
}

GOAL_CODE_MAP = {
    "hobby": "GOAL_HOBBY",
    "취미 합주": "GOAL_HOBBY",
    "취미": "GOAL_HOBBY",
    "busking": "GOAL_BUSKING_LIVE",
    "live": "GOAL_BUSKING_LIVE",
    "busking_live": "GOAL_BUSKING_LIVE",
    "버스킹 / 라이브": "GOAL_BUSKING_LIVE",
    "버스킹": "GOAL_BUSKING_LIVE",
    "band": "GOAL_BAND_PROJECT",
    "band_project": "GOAL_BAND_PROJECT",
    "밴드 프로젝트": "GOAL_BAND_PROJECT",
    "pro": "GOAL_PRO",
    "프로 지향": "GOAL_PRO",
}

PRACTICE_CODE_MAP = {
    "weekly_1": "PRACTICE_1",
    "practice_1": "PRACTICE_1",
    "주 1회": "PRACTICE_1",
    "weekly_2": "PRACTICE_2",
    "practice_2": "PRACTICE_2",
    "주 2회": "PRACTICE_2",
    "weekly_3_plus": "PRACTICE_3_PLUS",
    "practice_3_plus": "PRACTICE_3_PLUS",
    "주 3회 이상": "PRACTICE_3_PLUS",
}

STYLE_CODE_MAP = {
    "precise": "STYLE_PRECISE",
    "정확한 연주 중심": "STYLE_PRECISE",
    "balanced": "STYLE_BALANCED",
    "균형형": "STYLE_BALANCED",
    "expressive": "STYLE_EXPRESSIVE",
    "표현형": "STYLE_EXPRESSIVE",
}

AGE_CODE_MAP = {
    "20대": "AGE_20S",
    "age_20s": "AGE_20S",
    "30대": "AGE_30S",
    "age_30s": "AGE_30S",
    "40대": "AGE_40S",
    "age_40s": "AGE_40S",
    "50대 이상": "AGE_50_PLUS",
    "age_50_plus": "AGE_50_PLUS",
}

REGION_CODE_MAP = {
    "seoul": "SEOUL",
    "서울": "SEOUL",
}

DRINK_CODE_MAP = {
    "drink_enjoy": "DRINK_ENJOY",
    "즐김": "DRINK_ENJOY",
    "drink_sometimes": "DRINK_SOMETIMES",
    "가끔 참여": "DRINK_SOMETIMES",
    "drink_depends": "DRINK_DEPENDS",
    "상황에 따라": "DRINK_DEPENDS",
    "drink_none": "DRINK_NONE",
    "참여하지 않음": "DRINK_NONE",
}

SMOKING_CODE_MAP = {
    "smoking": "SMOKING",
    "흡연": "SMOKING",
    "non_smoking": "NON_SMOKING",
    "비흡연": "NON_SMOKING",
    "smoking_irrelevant": "SMOKING_IRRELEVANT",
    "상관없음": "SMOKING_IRRELEVANT",
}

SOCIAL_CODE_MAP = {
    "social_active": "SOCIAL_ACTIVE",
    "적극적": "SOCIAL_ACTIVE",
    "social_normal": "SOCIAL_NORMAL",
    "보통": "SOCIAL_NORMAL",
    "social_minimal": "SOCIAL_MINIMAL",
    "최소 참여": "SOCIAL_MINIMAL",
    "social_none": "SOCIAL_NONE",
    "선호하지 않음": "SOCIAL_NONE",
}

MEAL_CODE_MAP = {
    "meal_like": "MEAL_LIKE",
    "좋아함": "MEAL_LIKE",
    "meal_sometimes": "MEAL_SOMETIMES",
    "가끔 참여": "MEAL_SOMETIMES",
    "meal_if_needed": "MEAL_IF_NEEDED",
    "필요 시 참여": "MEAL_IF_NEEDED",
    "meal_none": "MEAL_NONE",
    "선호하지 않음": "MEAL_NONE",
}

PRACTICE_ORDER = {
    "PRACTICE_1": 1,
    "PRACTICE_2": 2,
    "PRACTICE_3_PLUS": 3,
}

STYLE_ORDER = {
    "STYLE_PRECISE": 1,
    "STYLE_BALANCED": 2,
    "STYLE_EXPRESSIVE": 3,
}

AGE_ORDER = {
    "AGE_20S": 1,
    "AGE_30S": 2,
    "AGE_40S": 3,
    "AGE_50_PLUS": 4,
}


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    return [value] if value not in (None, "") else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_token(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_").upper()


def _map_code(value: Any, alias_map: dict[str, str]) -> str:
    text = _safe_text(value)
    if not text:
        return ""

    direct = _normalize_token(text)
    if direct in alias_map.values():
        return direct

    lowered = text.lower()
    if lowered in alias_map:
        return alias_map[lowered]

    return direct


def _map_many(values: Any, alias_map: dict[str, str]) -> list[str]:
    mapped: list[str] = []
    seen: set[str] = set()
    for item in _safe_list(values):
        code = _map_code(item, alias_map)
        if code and code not in seen:
            seen.add(code)
            mapped.append(code)
    return mapped


def _derive_goals(profile_data: dict[str, Any]) -> list[str]:
    activity_goal = profile_data.get("activityGoal")
    if isinstance(activity_goal, dict) and activity_goal.get("activityGoals") is not None:
        return _map_many(activity_goal.get("activityGoals"), GOAL_CODE_MAP)
    if profile_data.get("goals") is not None:
        return _map_many(profile_data.get("goals"), GOAL_CODE_MAP)
    if activity_goal is not None:
        return _map_many(activity_goal, GOAL_CODE_MAP)
    return []


def _derive_region(profile_data: dict[str, Any]) -> str:
    if profile_data.get("region"):
        return _map_code(profile_data.get("region"), REGION_CODE_MAP)

    perf = _safe_dict(profile_data.get("performancePreferences"))
    if perf.get("activityRegionSido"):
        return _map_code(perf.get("activityRegionSido"), REGION_CODE_MAP)
    if perf.get("activityRegion"):
        region_text = _safe_text(perf.get("activityRegion"))
        if region_text:
            return _map_code(region_text.split()[0], REGION_CODE_MAP)

    return ""


def _derive_practice(profile_data: dict[str, Any]) -> str:
    if profile_data.get("practiceFrequency"):
        return _map_code(profile_data.get("practiceFrequency"), PRACTICE_CODE_MAP)

    perf = _safe_dict(profile_data.get("performancePreferences"))
    return _map_code(perf.get("practiceFrequency"), PRACTICE_CODE_MAP)


def _derive_style(profile_data: dict[str, Any]) -> str:
    if profile_data.get("style"):
        return _map_code(profile_data.get("style"), STYLE_CODE_MAP)

    perf = _safe_dict(profile_data.get("performancePreferences"))
    return _map_code(perf.get("performanceStyle"), STYLE_CODE_MAP)


def _derive_age(profile_data: dict[str, Any]) -> str:
    if profile_data.get("averageAge"):
        return _map_code(profile_data.get("averageAge"), AGE_CODE_MAP)
    if profile_data.get("ageGroup"):
        return _map_code(profile_data.get("ageGroup"), AGE_CODE_MAP)
    return ""


def _derive_lifestyle(profile_data: dict[str, Any]) -> dict[str, str]:
    lifestyle = _safe_dict(profile_data.get("lifestyle"))
    return {
        "drink": _map_code(lifestyle.get("drink"), DRINK_CODE_MAP),
        "smoking": _map_code(lifestyle.get("smoking"), SMOKING_CODE_MAP),
        "social": _map_code(lifestyle.get("social"), SOCIAL_CODE_MAP),
        "meal": _map_code(lifestyle.get("meal"), MEAL_CODE_MAP),
    }


def _derive_recruiting_sessions(profile_data: dict[str, Any]) -> list[str]:
    sessions = _map_many(profile_data.get("recruitingSessions"), INSTRUMENT_CODE_MAP)
    if sessions:
        return sessions

    recruit_needs = _safe_list(profile_data.get("recruitNeeds"))
    return _map_many(
        [item.get("instrument") for item in recruit_needs if isinstance(item, dict)],
        INSTRUMENT_CODE_MAP,
    )


def normalize_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile_data, dict):
        raise ValueError("profile_data must be a dict")

    perf = _safe_dict(profile_data.get("performancePreferences"))

    return {
        "id": _safe_text(profile_data.get("id") or profile_data.get("teamId") or profile_data.get("userId")),
        "nickname": _safe_text(profile_data.get("nickname") or profile_data.get("teamName") or profile_data.get("name")),
        "type": _safe_text(profile_data.get("type") or ("TEAM" if profile_data.get("recruitingSessions") else "USER")),
        "instruments": _map_many(
            profile_data.get("playableInstruments") or profile_data.get("instruments"),
            INSTRUMENT_CODE_MAP,
        ),
        "parts": _safe_list(profile_data.get("primaryParts") or profile_data.get("parts")),
        "recruitingSessions": _derive_recruiting_sessions(profile_data),
        "genres": _map_many(
            profile_data.get("preferredGenres") or profile_data.get("genres"),
            GENRE_CODE_MAP,
        ),
        "goals": _derive_goals(profile_data),
        "practiceFrequency": _derive_practice(profile_data),
        "style": _derive_style(profile_data),
        "region": _derive_region(profile_data),
        "ageGroup": _derive_age(profile_data),
        "lifestyle": _derive_lifestyle(profile_data),
        "availableTimes": _safe_list(
            profile_data.get("availableTimes")
            or perf.get("availableTimeSlots")
            or profile_data.get("availability")
        ),
        "raw": profile_data,
    }


def _overlap_ratio(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / max(len(left_set), len(right_set))


def _goal_match(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    if not left_set or not right_set:
        return 0.0
    return 1.0 if left_set & right_set else 0.0


def _distance_score(left: str, right: str, order_map: dict[str, int]) -> float:
    if not left or not right or left not in order_map or right not in order_map:
        return 0.0
    diff = abs(order_map[left] - order_map[right])
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    return 0.0


def _region_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return 1.0 if left == right else 0.0


def _lifestyle_score(left: dict[str, str], right: dict[str, str]) -> float:
    scores: list[float] = []
    for key in ("drink", "smoking", "social", "meal"):
        left_value = _safe_text(left.get(key))
        right_value = _safe_text(right.get(key))
        if not left_value or not right_value:
            continue
        scores.append(1.0 if left_value == right_value else 0.5)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _session_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    return bool(left_set and right_set and left_set & right_set)


def hard_filter(profile: dict[str, Any], candidate: dict[str, Any], mode: str = "apply") -> tuple[bool, str]:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")

    normalized_profile = normalize_profile(profile)
    normalized_candidate = normalize_profile(candidate)

    if mode == "apply":
        passed = _session_overlap(
            normalized_profile.get("instruments", []),
            normalized_candidate.get("recruitingSessions", []),
        )
    else:
        passed = _session_overlap(
            normalized_profile.get("recruitingSessions", []),
            normalized_candidate.get("instruments", []),
        )

    return (True, "session_match") if passed else (False, "session_mismatch")


def _build_breakdown(profile: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    return {
        "genre_overlap": _overlap_ratio(profile.get("genres", []), candidate.get("genres", [])),
        "goal_match": _goal_match(profile.get("goals", []), candidate.get("goals", [])),
        "practice_similarity": _distance_score(
            _safe_text(profile.get("practiceFrequency")),
            _safe_text(candidate.get("practiceFrequency")),
            PRACTICE_ORDER,
        ),
        "style_similarity": _distance_score(
            _safe_text(profile.get("style")),
            _safe_text(candidate.get("style")),
            STYLE_ORDER,
        ),
        "age_similarity": _distance_score(
            _safe_text(profile.get("ageGroup")),
            _safe_text(candidate.get("ageGroup")),
            AGE_ORDER,
        ),
        "lifestyle_similarity": _lifestyle_score(
            _safe_dict(profile.get("lifestyle")),
            _safe_dict(candidate.get("lifestyle")),
        ),
        "region_match": _region_score(
            _safe_text(profile.get("region")),
            _safe_text(candidate.get("region")),
        ),
    }


def _compose_reasons(breakdown: dict[str, float], include_session_reason: bool, limit: int = 3) -> list[str]:
    weighted = sorted(
        ((key, breakdown.get(key, 0.0) * WEIGHTS[key]) for key in WEIGHTS if breakdown.get(key, 0.0) > 0),
        key=lambda item: item[1],
        reverse=True,
    )

    reasons: list[str] = []
    if include_session_reason:
        reasons.append(REASON_LABELS["session_match"])

    for key, _ in weighted:
        label = REASON_LABELS[key]
        if label not in reasons:
            reasons.append(label)
        if len(reasons) >= limit:
            break

    return reasons or ["기본 조건이 맞아요"]


def _score_breakdown(breakdown: dict[str, float]) -> tuple[int, dict[str, float]]:
    weighted_debug: dict[str, float] = {}
    raw_score = 0.0
    for key, weight in WEIGHTS.items():
        contribution = round(breakdown.get(key, 0.0) * weight, 4)
        weighted_debug[key] = contribution
        raw_score += contribution
    final_score = max(0, min(100, int(round(raw_score))))
    weighted_debug["raw_score"] = round(raw_score, 4)
    weighted_debug["final_score"] = float(final_score)
    return final_score, weighted_debug


def _score_mode(profile: dict[str, Any], candidate: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized_profile = normalize_profile(profile)
    normalized_candidate = normalize_profile(candidate)

    passed, _ = hard_filter(normalized_profile, normalized_candidate, mode=mode)
    if not passed:
        return {
            "score": 0,
            "reasons": ["모집 세션이 맞지 않아요"],
            "debug": {"excluded_by": "session_mismatch", "final_score": 0.0},
            "excluded": True,
        }

    breakdown = _build_breakdown(normalized_profile, normalized_candidate)
    final_score, weighted_debug = _score_breakdown(breakdown)
    reasons = _compose_reasons(breakdown, include_session_reason=True)

    return {
        "score": final_score,
        "reasons": reasons,
        "debug": weighted_debug,
        "excluded": False,
    }


def score_apply_mode(profile: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return _score_mode(profile, candidate, mode="apply")


def score_recruit_mode(profile: dict[str, Any], candidate: dict[str, Any], recruit_needs: list[dict] | None = None) -> dict[str, Any]:
    del recruit_needs
    return _score_mode(profile, candidate, mode="recruit")


def _extract_apply_features(profile: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    normalized_profile = normalize_profile(profile)
    normalized_candidate = normalize_profile(candidate)
    breakdown = _build_breakdown(normalized_profile, normalized_candidate)
    return {
        "session_overlap": 1.0 if _session_overlap(normalized_profile.get("instruments", []), normalized_candidate.get("recruitingSessions", [])) else 0.0,
        **breakdown,
    }


def _extract_recruit_features(profile: dict[str, Any], candidate: dict[str, Any], recruit_needs: list[dict] | None = None) -> dict[str, float]:
    del recruit_needs
    normalized_profile = normalize_profile(profile)
    normalized_candidate = normalize_profile(candidate)
    breakdown = _build_breakdown(normalized_profile, normalized_candidate)
    return {
        "session_overlap": 1.0 if _session_overlap(normalized_profile.get("recruitingSessions", []), normalized_candidate.get("instruments", [])) else 0.0,
        **breakdown,
    }


def get_top_matches(
    profile_data: dict[str, Any],
    candidates: list[dict[str, Any]],
    mode: str = "apply",
    min_score: int = 0,
    top_k: int = 20,
    viewer_id: str = "anonymous",
    enable_feature_logging: bool = False,
) -> list[dict[str, Any]]:
    del viewer_id, enable_feature_logging

    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    if min_score < 0:
        raise ValueError("min_score must be >= 0")
    if top_k < 0:
        raise ValueError("top_k must be >= 0")

    normalized_profile = normalize_profile(profile_data)
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        normalized_candidate = normalize_profile(candidate)
        if mode == "apply":
            scored = score_apply_mode(normalized_profile, normalized_candidate)
        else:
            scored = score_recruit_mode(normalized_profile, normalized_candidate, normalized_profile.get("raw", {}).get("recruitNeeds", []))

        if scored.get("excluded"):
            continue

        score = int(scored.get("score", 0))
        if score < min_score:
            continue

        debug = dict(scored.get("debug", {}))
        debug["rule_score"] = float(score)
        debug["final_score"] = float(score)

        results.append(
            {
                "id": normalized_candidate.get("id") or _safe_text(candidate.get("id")),
                "nickname": normalized_candidate.get("nickname") or _safe_text(candidate.get("nickname")) or "Unknown",
                "matchScore": score,
                "reasons": list(scored.get("reasons", [])),
                "debug": debug,
            }
        )

    results.sort(key=lambda item: (-int(item["matchScore"]), item["id"]))
    return results[:top_k]

