from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
FEATURE_LOG_PATH = LOG_DIR / "match_features.jsonl"
EVENT_LOG_PATH = LOG_DIR / "match_events.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def log_match_features(
    *,
    recommendation_id: str,
    viewer_id: str,
    candidate_id: str,
    mode: str,
    rule_score: int,
    final_score: int,
    rank_position: int,
    features: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    ranking_version: str,
) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "recommendation_id": recommendation_id,
        "viewer_id": viewer_id,
        "candidate_id": candidate_id,
        "mode": mode,
        "rule_score": rule_score,
        "final_score": final_score,
        "rank_position": rank_position,
        "features": features,
        "candidate_snapshot": candidate_snapshot,
        "ranking_version": ranking_version,
    }
    _append_jsonl(FEATURE_LOG_PATH, payload)


def log_match_event(
    *,
    viewer_id: str,
    candidate_id: str,
    recommendation_id: str,
    event_type: str,
    mode: str,
    match_score: int | None = None,
    rank_position: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "viewer_id": viewer_id,
        "candidate_id": candidate_id,
        "recommendation_id": recommendation_id,
        "event_type": event_type,
        "mode": mode,
        "matchScore": match_score,
        "rank_position": rank_position,
        "extra": extra or {},
    }
    _append_jsonl(EVENT_LOG_PATH, payload)


def export_logs_to_csv(output_dir: Path | None = None) -> dict[str, Path]:
    output_dir = output_dir or LOG_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_rows = _load_jsonl(FEATURE_LOG_PATH)
    event_rows = _load_jsonl(EVENT_LOG_PATH)

    feature_csv = output_dir / "match_features.csv"
    event_csv = output_dir / "match_events.csv"

    def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        keys: set[str] = set()
        for row in rows:
            keys.update(row.keys())
        fieldnames = sorted(keys)
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                flat: dict[str, Any] = {}
                for key in fieldnames:
                    value = row.get(key)
                    if isinstance(value, (dict, list)):
                        flat[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        flat[key] = value
                writer.writerow(flat)

    write_rows(feature_csv, feature_rows)
    write_rows(event_csv, event_rows)
    return {"features": feature_csv, "events": event_csv}


def export_logs_to_parquet(output_dir: Path | None = None) -> dict[str, Path]:
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("export_logs_to_parquet requires pandas and pyarrow/fastparquet.") from exc

    output_dir = output_dir or LOG_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_rows = _load_jsonl(FEATURE_LOG_PATH)
    event_rows = _load_jsonl(EVENT_LOG_PATH)

    feature_parquet = output_dir / "match_features.parquet"
    event_parquet = output_dir / "match_events.parquet"

    pd.DataFrame(feature_rows).to_parquet(feature_parquet, index=False)
    pd.DataFrame(event_rows).to_parquet(event_parquet, index=False)

    return {"features": feature_parquet, "events": event_parquet}
