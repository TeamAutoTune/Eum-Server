from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.matching import MatchingProfile
from app.models.user import User

_BAND_MATCHING_PATH = Path(__file__).resolve().parents[3] / "band_matching"


def _safe_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _build_profile(candidate: dict) -> dict:
    instruments = _safe_list(candidate.get("instruments"))
    parts = _safe_list(candidate.get("parts"))

    primary_parts = []
    for idx, _ in enumerate(instruments):
        primary_parts.append(parts[idx] if idx < len(parts) else "")

    required_conditions = []
    for tag in _safe_list(candidate.get("tags")):
        if tag in {"punctual", "no_smoking", "owns_gear", "long_term", "weekend_only"}:
            required_conditions.append(tag)

    return {
        "playableInstruments": instruments,
        "primaryParts": primary_parts,
        "preferredGenres": _safe_list(candidate.get("genres")),
        "lifeSongs": ["N/A"],
        "favoriteArtists": ["N/A"],
        "performancePreferences": {
            "performanceStyle": candidate.get("style") or "balanced",
            "activityRegion": candidate.get("region") or "",
            "activityRegionSido": candidate.get("regionSido") or "",
            "activityRegionSigungu": candidate.get("regionSigungu") or "",
            "availableTimeSlots": _safe_list(candidate.get("availability")),
            "practiceFrequency": candidate.get("practiceFrequency") or "weekly_1",
        },
        "activityGoal": {
            "activityGoals": [candidate.get("activityGoal") or "hobby"],
        },
        "matchConditions": {
            "requiredConditions": required_conditions,
            "avoidConditions": [],
        },
    }


def seed(n: int = 100, seed_value: int = 42) -> None:
    if str(_BAND_MATCHING_PATH) not in sys.path:
        sys.path.insert(0, str(_BAND_MATCHING_PATH))

    from synthetic_data import generate_candidates  # type: ignore

    Base.metadata.create_all(bind=engine)

    candidates = generate_candidates(n=n, seed=seed_value)

    db = SessionLocal()
    try:
        for index, candidate in enumerate(candidates, start=1):
            login_id = f"seed_{index:03d}"
            nickname = str(candidate.get("nickname") or f"SeedUser{index:03d}")

            user = db.scalar(select(User).where(User.user_id == login_id))
            if not user:
                user = User(
                    nickname=nickname,
                    user_id=login_id,
                    hashed_password=hash_password("seed1234"),
                    instrument=(_safe_list(candidate.get("instruments")) or ["Unknown"])[0],
                )
                db.add(user)
                db.flush()
            else:
                user.nickname = nickname
                user.instrument = (_safe_list(candidate.get("instruments")) or ["Unknown"])[0]

            profile_data = _build_profile(candidate)
            profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
            candidate_payload = {
                "instruments": _safe_list(candidate.get("instruments")),
                "parts": _safe_list(candidate.get("parts")),
                "genres": _safe_list(candidate.get("genres")),
                "style": candidate.get("style") or "",
                "region": candidate.get("region") or "",
                "regionSido": candidate.get("regionSido") or "",
                "regionSigungu": candidate.get("regionSigungu") or "",
                "availability": _safe_list(candidate.get("availability")),
                "practiceFrequency": candidate.get("practiceFrequency") or "",
                "activityGoal": candidate.get("activityGoal") or "",
                "tags": _safe_list(candidate.get("tags")),
            }

            if not profile:
                profile = MatchingProfile(
                    user_id=user.id,
                    profile_data=profile_data,
                    candidate_data=candidate_payload,
                )
                db.add(profile)
            else:
                profile.profile_data = profile_data
                profile.candidate_data = candidate_payload

        db.commit()
        print(f"Seeded {n} users and matching profiles.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
