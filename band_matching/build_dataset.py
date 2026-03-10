# -*- coding: utf-8 -*-
"""Build training dataset from feature logs and event logs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

FEATURE_LOG_PATH = Path("logs/match_features.jsonl")
EVENT_LOG_PATH = Path("logs/match_events.jsonl")
OUTPUT_CSV_PATH = Path("logs/training_dataset.csv")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file into list of dicts."""
    if not path.exists():
        raise ValueError(f"File not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def make_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """Build join key."""
    return (
        str(row.get("viewer_id", "")),
        str(row.get("candidate_id", "")),
        str(row.get("mode", "")),
    )


def event_to_label(events: set[str]) -> int:
    """Convert event set to training label."""
    if "accepted" in events:
        return 3
    if "chat_started" in events:
        return 2
    if "profile_clicked" in events:
        return 1
    return 0


def build_dataset(
    feature_log_path: Path = FEATURE_LOG_PATH,
    event_log_path: Path = EVENT_LOG_PATH,
    output_csv_path: Path = OUTPUT_CSV_PATH,
) -> Path:
    """Build merged dataset CSV."""
    feature_rows = load_jsonl(feature_log_path)
    event_rows = load_jsonl(event_log_path)

    event_map: dict[tuple[str, str, str], set[str]] = {}

    for row in event_rows:
        key = make_key(row)
        event_type = str(row.get("event_type", "")).strip()
        if not event_type:
            continue
        event_map.setdefault(key, set()).add(event_type)

    dataset_rows: list[dict[str, Any]] = []
    feature_keys: set[str] = set()

    for row in feature_rows:
        key = make_key(row)
        features = row.get("features", {}) or {}
        if not isinstance(features, dict):
            features = {}

        feature_keys.update(features.keys())

        events = event_map.get(key, set())
        label = event_to_label(events)

        dataset_rows.append(
            {
                "viewer_id": key[0],
                "candidate_id": key[1],
                "mode": key[2],
                "rule_score": row.get("rule_score", 0),
                "label": label,
                "event_count": len(events),
                "events": "|".join(sorted(events)),
                "features": features,
            }
        )

    ordered_feature_keys = sorted(feature_keys)
    fieldnames = [
        "viewer_id",
        "candidate_id",
        "mode",
        "rule_score",
        "label",
        "event_count",
        "events",
        *ordered_feature_keys,
    ]

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with output_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in dataset_rows:
            flat_row = {
                "viewer_id": row["viewer_id"],
                "candidate_id": row["candidate_id"],
                "mode": row["mode"],
                "rule_score": row["rule_score"],
                "label": row["label"],
                "event_count": row["event_count"],
                "events": row["events"],
            }
            for key in ordered_feature_keys:
                flat_row[key] = row["features"].get(key, "")
            writer.writerow(flat_row)

    return output_csv_path


if __name__ == "__main__":
    output_path = build_dataset()
    print(f"Dataset saved to: {output_path}")