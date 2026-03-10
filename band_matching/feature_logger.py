# -*- coding: utf-8 -*-
"""Feature logging utilities for future ML training."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LOG_DIR = Path("logs")
DEFAULT_FEATURE_LOG_PATH = DEFAULT_LOG_DIR / "match_features.jsonl"
DEFAULT_EVENT_LOG_PATH = DEFAULT_LOG_DIR / "match_events.jsonl"


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def ensure_log_dir(path: Path) -> None:
    """Create parent directory if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one JSON row to a JSONL file."""
    ensure_log_dir(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def log_match_features(
    *,
    viewer_id: str,
    candidate_id: str,
    mode: str,
    features: dict[str, Any],
    rule_score: int,
    log_path: Path = DEFAULT_FEATURE_LOG_PATH,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log ranking-time features for future ML training."""
    payload = {
        "timestamp": _utc_now_iso(),
        "viewer_id": viewer_id,
        "candidate_id": candidate_id,
        "mode": mode,
        "features": features,
        "rule_score": rule_score,
    }
    if extra:
        payload.update(extra)

    append_jsonl(log_path, payload)


def log_match_event(
    *,
    viewer_id: str,
    candidate_id: str,
    event_type: str,
    mode: str,
    log_path: Path = DEFAULT_EVENT_LOG_PATH,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log user behavior events such as click/chat/skip."""
    payload = {
        "timestamp": _utc_now_iso(),
        "viewer_id": viewer_id,
        "candidate_id": candidate_id,
        "event_type": event_type,
        "mode": mode,
    }
    if extra:
        payload.update(extra)

    append_jsonl(log_path, payload)


def export_jsonl_to_csv(
    jsonl_path: Path = DEFAULT_FEATURE_LOG_PATH,
    csv_path: Path | None = None,
) -> Path:
    """Export feature JSONL logs to flat CSV for quick inspection."""
    if csv_path is None:
        csv_path = jsonl_path.with_suffix(".csv")

    if not jsonl_path.exists():
        raise ValueError(f"Log file not found: {jsonl_path}")

    rows: list[dict[str, Any]] = []
    feature_keys: set[str] = set()

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            features = obj.get("features", {}) or {}
            feature_keys.update(features.keys())
            rows.append(obj)

    feature_columns = sorted(feature_keys)
    base_columns = ["timestamp", "viewer_id", "candidate_id", "mode", "rule_score"]
    all_columns = base_columns + feature_columns

    ensure_log_dir(csv_path)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()

        for row in rows:
            features = row.get("features", {}) or {}
            flat_row = {
                "timestamp": row.get("timestamp", ""),
                "viewer_id": row.get("viewer_id", ""),
                "candidate_id": row.get("candidate_id", ""),
                "mode": row.get("mode", ""),
                "rule_score": row.get("rule_score", 0),
            }
            for key in feature_columns:
                flat_row[key] = features.get(key, "")
            writer.writerow(flat_row)

    return csv_path