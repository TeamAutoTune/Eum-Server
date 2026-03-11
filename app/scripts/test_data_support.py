from __future__ import annotations

import csv
import json
import random
from pathlib import Path

INSTRUMENT_PARTS: dict[str, list[str]] = {
    "guitar": ["lead", "rhythm", "acoustic"],
    "bass": ["finger", "pick"],
    "drum": ["main"],
    "vocal": ["main", "chorus"],
    "keyboard": ["piano", "synth"],
}
GENRES = ["rock", "pop", "indie", "jazz", "metal", "ballad", "funk", "blues"]
TIME_SLOTS = ["weekday_evening", "weekday_night", "weekend_day", "weekend_evening"]
PRACTICE_FREQUENCIES = ["weekly_1", "weekly_2", "weekly_3_plus"]
PERFORMANCE_STYLES = ["precise", "balanced", "expressive"]
ACTIVITY_GOALS = ["hobby", "busking", "band", "pro"]
AGE_GROUPS = ["20대", "30대", "40대"]
DRINK_OPTIONS = ["never", "sometimes", "often"]
SMOKING_OPTIONS = ["no", "sometimes", "yes"]
SOCIAL_OPTIONS = ["low", "medium", "high"]
DINING_OPTIONS = ["light", "medium", "heavy"]
SEOUL_SIGUNGU = ["강남구", "마포구", "송파구", "영등포구", "서초구", "관악구", "광진구", "성동구"]
GYEONGGI_SIGUNGU = ["수원시", "성남시", "고양시", "용인시"]
INCHEON_SIGUNGU = ["연수구", "남동구", "부평구"]


def build_user_id(prefix: str, index: int) -> str:
    return f"{prefix}_user_{index:03d}"


def build_nickname(prefix: str, index: int) -> str:
    return f"{prefix}_nick_{index:03d}"


def build_team_name(prefix: str, index: int) -> str:
    return f"{prefix}_team_{index:03d}"


def build_export_path(prefix: str, output_dir: str | Path, extension: str) -> Path:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{prefix}_seed_export.{extension}"


def choose_region(rng: random.Random) -> tuple[str, str, str]:
    roll = rng.random()
    if roll < 0.75:
        sido = "서울특별시"
        sigungu = rng.choice(SEOUL_SIGUNGU)
    elif roll < 0.9:
        sido = "경기도"
        sigungu = rng.choice(GYEONGGI_SIGUNGU)
    else:
        sido = "인천광역시"
        sigungu = rng.choice(INCHEON_SIGUNGU)
    return sido, sigungu, f"{sido} {sigungu}"


def choose_instruments(rng: random.Random) -> list[str]:
    count = 1 if rng.random() < 0.65 else 2
    return rng.sample(list(INSTRUMENT_PARTS.keys()), k=count)


def choose_parts(instruments: list[str], rng: random.Random) -> list[str]:
    return [rng.choice(INSTRUMENT_PARTS[instrument]) for instrument in instruments]


def choose_genres(rng: random.Random) -> list[str]:
    return rng.sample(GENRES, k=rng.randint(1, 3))


def choose_goals(rng: random.Random) -> list[str]:
    return rng.sample(ACTIVITY_GOALS, k=rng.randint(1, 2))


def choose_time_slots(rng: random.Random) -> list[str]:
    return rng.sample(TIME_SLOTS, k=rng.randint(1, 3))


def generate_user_profile(prefix: str, index: int, rng: random.Random) -> tuple[dict, dict]:
    del prefix
    instruments = choose_instruments(rng)
    parts = choose_parts(instruments, rng)
    genres = choose_genres(rng)
    goals = choose_goals(rng)
    activity_region_sido, activity_region_sigungu, activity_region = choose_region(rng)
    available_slots = choose_time_slots(rng)
    practice_frequency = rng.choice(PRACTICE_FREQUENCIES)
    performance_style = rng.choice(PERFORMANCE_STYLES)
    age_group = rng.choice(AGE_GROUPS)
    lifestyle = {
        "drink": rng.choice(DRINK_OPTIONS),
        "smoking": rng.choice(SMOKING_OPTIONS),
        "social": rng.choice(SOCIAL_OPTIONS),
        "meal": rng.choice(DINING_OPTIONS),
    }

    profile_data = {
        "playableInstruments": instruments,
        "primaryParts": parts,
        "preferredGenres": genres,
        "ageGroup": age_group,
        "activityDuration": age_group,
        "performancePreferences": {
            "performanceStyle": performance_style,
            "activityRegion": activity_region,
            "activityRegionSido": activity_region_sido,
            "activityRegionSigungu": activity_region_sigungu,
            "availableTimeSlots": available_slots,
            "practiceFrequency": practice_frequency,
        },
        "activityGoal": {
            "activityGoals": goals,
        },
        "lifestyle": lifestyle,
        "matchConditions": {
            "requiredConditions": [],
            "avoidConditions": [],
        },
    }
    candidate_data = {
        "instruments": instruments,
        "parts": parts,
        "genres": genres,
        "style": performance_style,
        "region": activity_region,
        "regionSido": activity_region_sido,
        "regionSigungu": activity_region_sigungu,
        "availability": available_slots,
        "practiceFrequency": practice_frequency,
        "activityGoal": goals[0],
        "activityGoals": goals,
        "ageGroup": age_group,
        "drink": lifestyle["drink"],
        "smoking": lifestyle["smoking"],
        "social": lifestyle["social"],
        "meal": lifestyle["meal"],
        "tags": [],
    }
    return profile_data, candidate_data


def generate_team_seed(
    prefix: str,
    index: int,
    rng: random.Random,
) -> tuple[dict, dict, list[dict], str]:
    team_genres = choose_genres(rng)
    goals = choose_goals(rng)
    region_sido, region_sigungu, region_text = choose_region(rng)
    practice_frequency = rng.choice(PRACTICE_FREQUENCIES)
    average_age = rng.choice(AGE_GROUPS)
    recruiting_sessions = choose_instruments(rng)
    recruit_needs: list[dict] = []
    for instrument in rng.sample(list(INSTRUMENT_PARTS.keys()), k=rng.randint(1, 3)):
        recruit_needs.append(
            {
                "instrument": instrument,
                "part": rng.choice(INSTRUMENT_PARTS[instrument]),
                "count": rng.randint(1, 2),
                "required": rng.choice([True, False]),
            }
        )

    team_fields = {
        "team_name": build_team_name(prefix, index),
        "description": f"{prefix} seeded team {index:03d}",
        "average_age": average_age,
        "region": region_text,
        "genres": team_genres,
        "gender_ratio": rng.choice(["mixed", "male_majority", "female_majority"]),
        "reference_songs": rng.sample(
            [
                "New Rules",
                "Viva La Vida",
                "Dreams",
                "Take Five",
                "Yellow",
                "Come Together",
            ],
            k=2,
        ),
    }
    team_profile = {
        "teamProfile": {
            "genres": team_genres,
            "practiceFrequency": practice_frequency,
            "region": region_text,
            "regionSido": region_sido,
            "regionSigungu": region_sigungu,
            "averageAge": average_age,
            "activityGoal": {
                "activityGoals": goals,
            },
            "recruitingSessions": recruiting_sessions,
        },
        "genres": team_genres,
        "practiceFrequency": practice_frequency,
        "region": region_text,
        "regionSido": region_sido,
        "regionSigungu": region_sigungu,
        "averageAge": average_age,
        "activityGoal": {
            "activityGoals": goals,
        },
        "recruitingSessions": recruiting_sessions,
        "recruitNeeds": recruit_needs,
    }
    return team_fields, team_profile, recruit_needs, practice_frequency


def write_json_export(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_export(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
