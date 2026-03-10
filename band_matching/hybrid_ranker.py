# -*- coding: utf-8 -*-
"""Hybrid ranking using rule score + learned feature weights."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODEL_PATH = Path(__file__).resolve().parent / "logs" / "simple_model.json"


def load_model(model_path: Path = MODEL_PATH) -> dict[str, Any]:
    """Load learned model weights."""
    if not model_path.exists():
        raise ValueError(f"Model not found: {model_path}")

    with model_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except:
        return default


def compute_learned_score(
    features: dict[str, Any],
    feature_weights: dict[str, float],
) -> float:
    """Compute learned score from feature weights."""
    score = 0.0
    for feature_name, weight in feature_weights.items():
        value = to_float(features.get(feature_name, 0))
        score += value * weight
    return score * 100


def hybrid_score(
    rule_score: float,
    features: dict[str, Any],
    model: dict[str, Any],
    rule_weight: float = 0.7,
    learned_weight: float = 0.3,
) -> float:
    """Combine rule score with learned score."""
    weights = model["feature_weights"]

    learned_score = compute_learned_score(features, weights)

    final_score = (rule_score * rule_weight) + (learned_score * learned_weight)

    return round(final_score, 4)