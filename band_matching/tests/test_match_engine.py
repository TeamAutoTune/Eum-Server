# -*- coding: utf-8 -*-
from __future__ import annotations

from match_engine import (
    get_top_matches,
    hard_filter,
    normalize_profile,
    score_apply_mode,
    score_recruit_mode,
)


def make_profile() -> dict:
    return {
        "playableInstruments": ["Vocal", "Guitar"],
        "primaryParts": ["Main Vocal", "Rhythm Guitar"],
        "preferredGenres": ["Rock", "Indie", "Pop"],
        "lifeSongs": ["Song A"],
        "favoriteArtists": ["Artist A"],
        "performancePreferences": {
            "performanceStyle": "balanced",
            "activityRegion": "서울특별시 마포구",
            "activityRegionSido": "서울특별시",
            "activityRegionSigungu": "마포구",
            "availableTimeSlots": ["weekday_evening", "weekend_day"],
            "practiceFrequency": "weekly_2",
        },
        "activityGoal": {
            "activityGoals": ["hobby", "band"],
        },
        "matchConditions": {
            "requiredConditions": ["no_smoking", "punctual"],
            "avoidConditions": ["weekend_only"],
        },
        "recruitNeeds": [
            {"instrument": "Bass", "part": "Electric Bass", "count": 1, "required": True},
            {"instrument": "Drums", "part": "Acoustic Drums", "count": 1, "required": False},
        ],
    }


def make_candidate(**overrides) -> dict:
    base = {
        "id": "u-001",
        "nickname": "TestUser",
        "instruments": ["Vocal", "Bass"],
        "parts": ["Main Vocal", "Electric Bass"],
        "genres": ["Rock", "Indie"],
        "style": "balanced",
        "region": "서울특별시 강남구",
        "regionSido": "서울특별시",
        "regionSigungu": "강남구",
        "availability": ["weekday_evening", "weekend_day"],
        "practiceFrequency": "weekly_2",
        "activityGoal": "band",
        "tags": ["no_smoking", "punctual", "owns_gear"],
    }
    base.update(overrides)
    return base


def test_hard_filter_instrument_mismatch():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(instruments=["Drums"])
    passed, reason = hard_filter(profile, candidate)
    assert passed is False
    assert "악기" in reason


def test_hard_filter_region_sido_mismatch():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(
        region="경기도 성남시",
        regionSido="경기도",
        regionSigungu="성남시",
    )
    passed, reason = hard_filter(profile, candidate)
    assert passed is False
    assert "시/도" in reason


def test_same_sido_different_sigungu_passes():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(
        region="서울특별시 강남구",
        regionSido="서울특별시",
        regionSigungu="강남구",
    )
    passed, _ = hard_filter(profile, candidate)
    assert passed is True


def test_same_sigungu_bonus_applied():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(
        region="서울특별시 마포구",
        regionSido="서울특별시",
        regionSigungu="마포구",
    )
    scored = score_apply_mode(profile, candidate)
    assert scored["debug"]["same_sigungu_bonus"] > 0


def test_required_true_unmet_excluded_in_recruit_mode():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(instruments=["Vocal"], parts=["Main Vocal"])
    scored = score_recruit_mode(profile, candidate, profile["recruitNeeds"])
    assert scored["excluded"] is True
    assert scored["score"] == 0


def test_avoid_conflict_penalty_applied():
    profile = normalize_profile(make_profile())
    candidate_safe = make_candidate(tags=["no_smoking", "punctual"])
    candidate_conflict = make_candidate(tags=["no_smoking", "punctual", "weekend_only"])

    safe_score = score_apply_mode(profile, candidate_safe)["score"]
    conflict_score = score_apply_mode(profile, candidate_conflict)["score"]

    assert conflict_score < safe_score


def test_apply_and_recruit_modes_can_differ():
    profile_data = make_profile()
    candidate = make_candidate(
        id="u-123",
        instruments=["Guitar", "Bass"],
        parts=["Rhythm Guitar", "Electric Bass"],
    )
    apply_rows = get_top_matches(profile_data, [candidate], mode="apply", min_score=0, top_k=10)
    recruit_rows = get_top_matches(profile_data, [candidate], mode="recruit", min_score=0, top_k=10)

    assert len(apply_rows) == 1
    assert len(recruit_rows) == 1
    assert apply_rows[0]["matchScore"] != recruit_rows[0]["matchScore"]


def test_sorted_descending():
    profile_data = make_profile()
    candidate_low = make_candidate(
        id="u-100",
        nickname="Low",
        genres=["Ballad"],
        parts=["Sub Vocal"],
        availability=["weekday_night"],
        tags=[],
    )
    candidate_high = make_candidate(
        id="u-101",
        nickname="High",
        genres=["Rock", "Indie", "Pop"],
        parts=["Main Vocal", "Rhythm Guitar"],
        availability=["weekday_evening", "weekend_day"],
        region="서울특별시 마포구",
        regionSigungu="마포구",
        tags=["no_smoking", "punctual"],
    )

    rows = get_top_matches(profile_data, [candidate_low, candidate_high], mode="apply")
    assert rows[0]["id"] == "u-101"
    assert rows[0]["matchScore"] >= rows[1]["matchScore"]


def test_min_score_filter():
    profile_data = make_profile()
    low = make_candidate(
        id="u-200",
        genres=["Ballad"],
        parts=["Sub Vocal"],
        availability=["weekday_night"],
        tags=[],
    )
    rows = get_top_matches(profile_data, [low], mode="apply", min_score=50, top_k=10)
    assert rows == []


def test_top_k_limit():
    profile_data = make_profile()
    candidates = [make_candidate(id=f"u-{i:03d}", nickname=f"User{i}") for i in range(10)]
    rows = get_top_matches(profile_data, candidates, mode="apply", min_score=0, top_k=3)
    assert len(rows) == 3


def test_empty_inputs_safe():
    profile_data = make_profile()
    rows = get_top_matches(profile_data, [], mode="apply", min_score=0, top_k=10)
    assert rows == []


def test_score_range_clamped_0_to_100():
    profile = normalize_profile(make_profile())
    candidate = make_candidate(
        genres=["Rock", "Indie", "Pop"],
        parts=["Main Vocal", "Rhythm Guitar", "Electric Bass"],
        availability=["weekday_evening", "weekend_day"],
        region="서울특별시 마포구",
        regionSigungu="마포구",
        tags=["no_smoking", "punctual", "owns_gear"],
    )
    scored_apply = score_apply_mode(profile, candidate)
    scored_recruit = score_recruit_mode(profile, candidate, profile["recruitNeeds"])

    assert 0 <= scored_apply["score"] <= 100
    assert 0 <= scored_recruit["score"] <= 100


def test_region_fallback_from_sido_sigungu():
    profile_data = make_profile()
    profile_data["performancePreferences"]["activityRegion"] = ""
    candidate = make_candidate(
        region="서울특별시 강남구",
        regionSido="서울특별시",
        regionSigungu="강남구",
    )
    rows = get_top_matches(profile_data, [candidate], mode="apply")
    assert len(rows) == 1


def test_required_and_avoid_same_item_required_wins():
    profile_data = make_profile()
    profile_data["matchConditions"]["requiredConditions"] = ["no_smoking"]
    profile_data["matchConditions"]["avoidConditions"] = ["no_smoking", "weekend_only"]

    candidate = make_candidate(tags=["no_smoking"])
    rows = get_top_matches(profile_data, [candidate], mode="apply")
    assert len(rows) == 1
    assert rows[0]["matchScore"] > 0