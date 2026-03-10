# -*- coding: utf-8 -*-
"""Synthetic candidate generator for band matching."""

from __future__ import annotations

import random
from typing import Dict, List

INSTRUMENTS = [
    "Vocal",
    "Guitar",
    "Bass",
    "Drums",
    "Keyboard",
    "Piano",
    "Violin",
    "Saxophone",
    "Trumpet",
    "DJ",
]

PARTS_BY_INSTRUMENT = {
    "Vocal": ["Main Vocal", "Sub Vocal", "Chorus Vocal"],
    "Guitar": ["Lead Guitar", "Rhythm Guitar", "Acoustic Guitar"],
    "Bass": ["Electric Bass", "Fingerstyle Bass", "Slap Bass"],
    "Drums": ["Acoustic Drums", "Electronic Drums", "Percussion"],
    "Keyboard": ["Piano", "Synth", "Organ"],
    "Piano": ["Solo Piano", "Comping Piano", "Session Piano"],
    "Violin": ["Solo Violin", "Ensemble Violin", "String Arrangement"],
    "Saxophone": ["Alto Sax", "Tenor Sax", "Baritone Sax"],
    "Trumpet": ["Lead Trumpet", "Section Trumpet", "Improvisation Trumpet"],
    "DJ": ["Turntablism", "Live Mixing", "Electronic Set"],
}

GENRES = [
    "Rock",
    "Indie",
    "Ballad",
    "Jazz",
    "R&B",
    "Metal",
    "Pop",
    "HipHop",
    "Funk",
    "Electronic",
]

STYLES = ["precise", "balanced", "expressive"]
TIME_SLOTS = ["weekday_evening", "weekday_night", "weekend_day", "weekend_evening"]
PRACTICE_FREQUENCIES = ["weekly_1", "weekly_2", "weekly_3_plus"]
ACTIVITY_GOALS = ["hobby", "busking", "band", "pro"]
TAGS = ["weekend_only", "no_smoking", "owns_gear", "punctual", "long_term"]

REGIONS = [
    ("?????", "???"),
    ("?????", "???"),
    ("?????", "???"),
    ("?????", "????"),
    ("???", "???"),
    ("???", "???"),
    ("???", "???"),
    ("?????", "???"),
    ("?????", "????"),
    ("?????", "???"),
    ("?????", "???"),
    ("?????", "??"),
    ("?????", "??"),
    ("???????", "???"),
]

NICKNAME_PREFIXES = [
    "Blue",
    "Indie",
    "Groove",
    "Echo",
    "Mellow",
    "Wild",
    "Urban",
    "Neon",
    "Golden",
    "Silver",
]

NICKNAME_SUFFIXES = [
    "Tone",
    "Beat",
    "Chord",
    "Player",
    "Note",
    "Wave",
    "Jam",
    "Flow",
    "Stage",
    "Pulse",
]


def _weighted_region_choice(rng: random.Random) -> tuple[str, str]:
    weights = [16, 13, 10, 8, 10, 8, 7, 5, 6, 4, 4, 3, 3, 3]
    return rng.choices(REGIONS, weights=weights, k=1)[0]


def _weighted_instrument_choice(rng: random.Random) -> str:
    weights = {
        "Vocal": 18,
        "Guitar": 18,
        "Bass": 9,
        "Drums": 10,
        "Keyboard": 8,
        "Piano": 10,
        "Violin": 5,
        "Saxophone": 4,
        "Trumpet": 3,
        "DJ": 5,
    }
    instruments = list(weights.keys())
    probs = list(weights.values())
    return rng.choices(instruments, weights=probs, k=1)[0]


def _sample_unique(
    rng: random.Random,
    pool: list[str],
    min_count: int,
    max_count: int,
) -> list[str]:
    if not pool:
        return []
    count = rng.randint(min_count, min(max_count, len(pool)))
    return rng.sample(pool, count)


def _make_nickname(rng: random.Random, idx: int) -> str:
    return f"{rng.choice(NICKNAME_PREFIXES)}{rng.choice(NICKNAME_SUFFIXES)}{idx:03d}"


def generate_candidates(n: int = 100, seed: int = 42) -> List[Dict]:
    """Generate synthetic candidate list."""
    if n < 0:
        raise ValueError("n must be >= 0")

    rng = random.Random(seed)
    candidates: list[dict] = []

    for idx in range(1, n + 1):
        primary_instrument = _weighted_instrument_choice(rng)
        secondary_pool = [inst for inst in INSTRUMENTS if inst != primary_instrument]
        extra_count = rng.choices([0, 1, 2], weights=[70, 24, 6], k=1)[0]
        extra_instruments = rng.sample(secondary_pool, k=extra_count)
        instruments = [primary_instrument, *extra_instruments]

        parts: list[str] = []
        for inst in instruments:
            parts.extend(_sample_unique(rng, PARTS_BY_INSTRUMENT[inst], 1, 1))

        genres = _sample_unique(rng, GENRES, 1, 3)
        style = rng.choices(STYLES, weights=[30, 45, 25], k=1)[0]
        sido, sigungu = _weighted_region_choice(rng)
        region = f"{sido} {sigungu}"
        availability = _sample_unique(rng, TIME_SLOTS, 1, 3)
        practice_frequency = rng.choices(
            PRACTICE_FREQUENCIES, weights=[30, 45, 25], k=1
        )[0]
        activity_goal = rng.choices(
            ACTIVITY_GOALS, weights=[40, 15, 30, 15], k=1
        )[0]
        tags = _sample_unique(rng, TAGS, 0, 3)

        candidates.append(
            {
                "id": f"u-{idx:03d}",
                "nickname": _make_nickname(rng, idx),
                "instruments": instruments,
                "parts": parts,
                "genres": genres,
                "style": style,
                "region": region,
                "regionSido": sido,
                "regionSigungu": sigungu,
                "availability": availability,
                "practiceFrequency": practice_frequency,
                "activityGoal": activity_goal,
                "tags": tags,
            }
        )

    return candidates


if __name__ == "__main__":
    for row in generate_candidates(5, seed=42):
        print(row)