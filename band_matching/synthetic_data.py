"""Synthetic data helpers for the new band matching engine."""

from __future__ import annotations

import random
from typing import Any

INSTRUMENTS = [
    "VOCAL",
    "GUITAR",
    "BASS",
    "DRUM",
    "KEYBOARD",
    "PIANO",
    "VIOLIN",
    "SAXOPHONE",
    "TRUMPET",
    "DJ",
]

GENRES = [
    "ROCK",
    "INDIE",
    "BALLAD",
    "JAZZ",
    "RNB",
    "METAL",
    "POP",
    "HIPHOP",
    "FUNK",
    "ELECTRONIC",
]

GOALS = [
    "GOAL_HOBBY",
    "GOAL_BUSKING_LIVE",
    "GOAL_BAND_PROJECT",
    "GOAL_PRO",
]

PRACTICES = ["PRACTICE_1", "PRACTICE_2", "PRACTICE_3_PLUS"]
STYLES = ["STYLE_PRECISE", "STYLE_BALANCED", "STYLE_EXPRESSIVE"]
AGES = ["AGE_20S", "AGE_30S", "AGE_40S", "AGE_50_PLUS"]

LIFESTYLE_CHOICES = {
    "drink": ["DRINK_ENJOY", "DRINK_SOMETIMES", "DRINK_DEPENDS", "DRINK_NONE"],
    "smoking": ["SMOKING", "NON_SMOKING", "SMOKING_IRRELEVANT"],
    "social": ["SOCIAL_ACTIVE", "SOCIAL_NORMAL", "SOCIAL_MINIMAL", "SOCIAL_NONE"],
    "meal": ["MEAL_LIKE", "MEAL_SOMETIMES", "MEAL_IF_NEEDED", "MEAL_NONE"],
}


def _sample_unique(rng: random.Random, pool: list[str], min_count: int, max_count: int) -> list[str]:
    count = rng.randint(min_count, min(max_count, len(pool)))
    return rng.sample(pool, count)


def _make_lifestyle(rng: random.Random) -> dict[str, str]:
    return {key: rng.choice(values) for key, values in LIFESTYLE_CHOICES.items()}


def generate_candidates(n: int = 100, seed: int = 42) -> list[dict[str, Any]]:
    if n < 0:
        raise ValueError("n must be >= 0")

    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for idx in range(1, n + 1):
        rows.append(
            {
                "id": f"user_{idx:03d}",
                "nickname": f"User{idx:03d}",
                "instruments": _sample_unique(rng, INSTRUMENTS, 1, 3),
                "genres": _sample_unique(rng, GENRES, 1, 3),
                "goals": _sample_unique(rng, GOALS, 1, 2),
                "practiceFrequency": rng.choice(PRACTICES),
                "style": rng.choice(STYLES),
                "region": "SEOUL",
                "ageGroup": rng.choice(AGES),
                "lifestyle": _make_lifestyle(rng),
            }
        )
    return rows

