# -*- coding: utf-8 -*-
"""Example usage for band match engine."""

from __future__ import annotations

from pprint import pprint

from feature_logger import log_match_event
from match_engine import get_top_matches
from synthetic_data import generate_candidates

APPLY_PROFILE = {
    "playableInstruments": ["Vocal", "Guitar"],
    "primaryParts": ["Main Vocal", "Rhythm Guitar"],
    "preferredGenres": ["Rock", "Indie", "Pop"],
    "lifeSongs": ["Yellow", "Dreams", "Fix You"],
    "favoriteArtists": ["Coldplay", "Oasis", "Day6"],
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
    "recruitNeeds": [],
}

RECRUIT_PROFILE = {
    "playableInstruments": ["Guitar"],
    "primaryParts": ["Rhythm Guitar"],
    "preferredGenres": ["Rock", "Metal", "Indie"],
    "lifeSongs": ["Master of Puppets", "Everlong", "Time of Dying"],
    "favoriteArtists": ["Metallica", "Foo Fighters", "Nirvana"],
    "performancePreferences": {
        "performanceStyle": "precise",
        "activityRegion": "",
        "activityRegionSido": "서울특별시",
        "activityRegionSigungu": "강남구",
        "availableTimeSlots": ["weekday_evening", "weekend_evening"],
        "practiceFrequency": "weekly_2",
    },
    "activityGoal": {
        "activityGoals": ["band", "pro"],
    },
    "matchConditions": {
        "requiredConditions": ["owns_gear", "punctual"],
        "avoidConditions": ["weekend_only"],
    },
    "recruitNeeds": [
        {"instrument": "Bass", "part": "Electric Bass", "count": 1, "required": True},
        {"instrument": "Drums", "part": "Acoustic Drums", "count": 1, "required": False},
    ],
}


def print_block(title: str, rows: list[dict]) -> None:
    print(f"\n=== {title} ===")
    for idx, row in enumerate(rows, start=1):
        print(f"\n[{idx}] {row['nickname']} ({row['id']})")
        print(f"matchScore: {row['matchScore']}")
        print("reasons:")
        for reason in row["reasons"]:
            print(f" - {reason}")
        print("debug:")
        pprint(row["debug"])


def simulate_user_events(matches: list[dict], viewer_id: str, mode: str) -> None:
    for row in matches:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=row["id"],
            event_type="match_shown",
            mode=mode,
            extra={"matchScore": row["matchScore"]},
        )

    if matches:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[0]["id"],
            event_type="profile_clicked",
            mode=mode,
        )
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[0]["id"],
            event_type="chat_started",
            mode=mode,
        )

    if len(matches) > 1:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[1]["id"],
            event_type="skip",
            mode=mode,
        )


def main() -> None:
    candidates = generate_candidates(n=100, seed=42)

    apply_matches = get_top_matches(
        profile_data=APPLY_PROFILE,
        candidates=candidates,
        mode="apply",
        min_score=20,
        top_k=5,
        viewer_id="viewer-apply-001",
        enable_feature_logging=True,
    )

    recruit_matches = get_top_matches(
        profile_data=RECRUIT_PROFILE,
        candidates=candidates,
        mode="recruit",
        min_score=20,
        top_k=5,
        viewer_id="viewer-recruit-001",
        enable_feature_logging=True,
    )

    simulate_user_events(apply_matches, "viewer-apply-001", "apply")
    simulate_user_events(recruit_matches, "viewer-recruit-001", "recruit")

    print_block("APPLY MODE TOP 5", apply_matches)
    print_block("RECRUIT MODE TOP 5", recruit_matches)
    
def simulate_user_events(matches: list[dict], viewer_id: str, mode: str) -> None:
    for row in matches:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=row["id"],
            event_type="match_shown",
            mode=mode,
            extra={"matchScore": row["matchScore"]},
        )

    if matches:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[0]["id"],
            event_type="profile_clicked",
            mode=mode,
        )
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[0]["id"],
            event_type="chat_started",
            mode=mode,
        )

    if len(matches) > 1:
        log_match_event(
            viewer_id=viewer_id,
            candidate_id=matches[1]["id"],
            event_type="skip",
            mode=mode,
        )


if __name__ == "__main__":
    main()