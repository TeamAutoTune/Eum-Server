# -*- coding: utf-8 -*-
"""Simple training pipeline for future learned ranking expansion.

Current version:
- loads training_dataset.csv
- builds a simple weighted baseline from historical labels
- prints feature statistics
- saves learned weights as JSON

This is not a production ML model yet.
It is a lightweight bridge between rule-based ranking and future ML ranking.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any

DATASET_PATH = Path("logs/training_dataset.csv")
MODEL_PATH = Path("logs/simple_model.json")

META_COLUMNS = {
    "viewer_id",
    "candidate_id",
    "mode",
    "rule_score",
    "label",
    "event_count",
    "events",
}


def load_dataset(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    """Load CSV dataset."""
    if not path.exists():
        raise ValueError(f"Dataset file not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_feature_columns(rows: list[dict[str, Any]]) -> list[str]:
    """Extract feature columns from dataset."""
    if not rows:
        return []
    return [col for col in rows[0].keys() if col not in META_COLUMNS]


def compute_feature_weights(
    rows: list[dict[str, Any]],
    feature_columns: list[str],
) -> dict[str, float]:
    """Learn simple feature weights from label averages.

    Method:
    - For each feature column, compare average value in positive rows vs all rows
    - Use the gap as a crude importance signal
    """
    if not rows:
        return {}

    positive_rows = [row for row in rows if to_float(row.get("label", 0)) >= 1]
    strong_rows = [row for row in rows if to_float(row.get("label", 0)) >= 2]

    weights: dict[str, float] = {}

    for col in feature_columns:
        all_avg = mean(to_float(row.get(col, 0)) for row in rows)
        pos_avg = mean(to_float(row.get(col, 0)) for row in positive_rows) if positive_rows else 0.0
        strong_avg = mean(to_float(row.get(col, 0)) for row in strong_rows) if strong_rows else 0.0

        # strong behavior 가중치를 조금 더 높게 본다
        weight = ((pos_avg - all_avg) * 0.4) + ((strong_avg - all_avg) * 0.6)
        weights[col] = round(weight, 6)

    return weights


def score_row(
    row: dict[str, Any],
    feature_weights: dict[str, float],
    rule_score_weight: float = 0.7,
    learned_score_weight: float = 0.3,
) -> float:
    """Compute hybrid score from rule score + learned feature score."""
    rule_score = to_float(row.get("rule_score", 0))

    learned_score = 0.0
    for feature_name, weight in feature_weights.items():
        learned_score += to_float(row.get(feature_name, 0)) * weight

    # learned_score를 보기 쉽게 0~100 scale 비슷하게 키운다
    learned_score_scaled = learned_score * 100

    final_score = (rule_score * rule_score_weight) + (learned_score_scaled * learned_score_weight)
    return round(final_score, 4)


def summarize_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return dataset summary."""
    if not rows:
        return {
            "row_count": 0,
            "label_distribution": {},
        }

    label_counts: dict[str, int] = {}
    for row in rows:
        label = str(int(to_float(row.get("label", 0))))
        label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "row_count": len(rows),
        "label_distribution": label_counts,
    }


def save_model(
    model_path: Path,
    feature_weights: dict[str, float],
    feature_columns: list[str],
    dataset_summary: dict[str, Any],
) -> Path:
    """Save learned baseline model."""
    model_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "model_type": "simple_weighted_baseline",
        "feature_columns": feature_columns,
        "feature_weights": feature_weights,
        "dataset_summary": dataset_summary,
    }

    with model_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return model_path


def main() -> None:
    rows = load_dataset(DATASET_PATH)
    summary = summarize_dataset(rows)

    print("=== DATASET SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    feature_columns = get_feature_columns(rows)
    print("\n=== FEATURE COLUMNS ===")
    for col in feature_columns:
        print("-", col)

    feature_weights = compute_feature_weights(rows, feature_columns)

    print("\n=== LEARNED FEATURE WEIGHTS ===")
    for key, value in sorted(feature_weights.items(), key=lambda x: x[1], reverse=True):
        print(f"{key}: {value:.6f}")

    print("\n=== SAMPLE HYBRID SCORES (TOP 10) ===")
    scored_rows = []
    for row in rows:
        hybrid_score = score_row(row, feature_weights)
        scored_rows.append(
            {
                "viewer_id": row.get("viewer_id", ""),
                "candidate_id": row.get("candidate_id", ""),
                "mode": row.get("mode", ""),
                "label": int(to_float(row.get("label", 0))),
                "rule_score": to_float(row.get("rule_score", 0)),
                "hybrid_score": hybrid_score,
            }
        )

    scored_rows.sort(key=lambda x: x["hybrid_score"], reverse=True)

    for row in scored_rows[:10]:
        print(row)

    saved_path = save_model(MODEL_PATH, feature_weights, feature_columns, summary)
    print(f"\nModel saved to: {saved_path}")


if __name__ == "__main__":
    main()