from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.llm_service import (
    LLMAuthError,
    LLMConfigError,
    LLMExternalAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    chat,
)

logger = logging.getLogger(__name__)


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    text = str(value).strip()
    return [text] if text else []


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_recruiting_parts(candidate: dict[str, Any]) -> list[str]:
    recruit_needs = candidate.get("recruitNeeds")
    if not isinstance(recruit_needs, list):
        return []

    parts: list[str] = []
    for item in recruit_needs:
        if not isinstance(item, dict):
            continue
        instrument = _safe_text(item.get("instrument"))
        part = _safe_text(item.get("part"))
        joined = " ".join(part for part in [instrument, part] if part)
        if joined:
            parts.append(joined)
    return parts


def _build_prompt_payload(
    *,
    mode: str,
    card: dict[str, Any],
    candidate: dict[str, Any],
    nickname: str,
) -> dict[str, Any]:
    base = {
        "card_type": "team" if mode == "apply" else "user",
        "nickname": _safe_text(nickname),
        "team_name": _safe_text(card.get("team_name") or candidate.get("team_name") or candidate.get("teamName")),
        "instruments": _safe_list(card.get("instruments")),
        "parts": _safe_list(card.get("parts")),
        "genres": _safe_list(card.get("genres")),
        "style": _safe_text(card.get("style")),
        "region": _safe_text(card.get("region")),
        "availability": _safe_list(card.get("availability")),
        "practiceFrequency": _safe_text(card.get("practiceFrequency")),
        "activityGoal": _safe_text(card.get("activityGoal")),
        "recruiting_parts": _extract_recruiting_parts(candidate),
    }
    return {key: value for key, value in base.items() if value not in ("", [], None)}


def _has_summary_material(payload: dict[str, Any]) -> bool:
    keys = {"instruments", "parts", "genres", "region", "availability", "practiceFrequency", "activityGoal", "recruiting_parts"}
    return any(payload.get(key) for key in keys)


def _build_prompt(payload: dict[str, Any]) -> str:
    return (
        "아래 JSON 카드 데이터만 사용해서 한국어 소개 문장 1문장을 작성하세요.\n"
        "규칙:\n"
        "- 입력에 없는 사실은 절대 추가하지 말 것\n"
        "- 과장/광고 문구 금지\n"
        "- 자연스러운 앱 프로필 소개 톤\n"
        "- 50~80자 내외\n"
        '- 반드시 "입니다"체로 끝낼 것\n'
        "- 출력은 문장 하나만, 따옴표/개행/불릿 없이\n\n"
        f"카드 데이터(JSON):\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _normalize_summary(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.strip()).strip("\"' ")
    if not normalized:
        return None

    if "\n" in normalized:
        normalized = normalized.splitlines()[0].strip()

    if "。" in normalized:
        normalized = normalized.split("。", 1)[0].strip()
    if "." in normalized:
        normalized = normalized.split(".", 1)[0].strip()

    if not normalized.endswith("입니다"):
        if normalized.endswith("입니다."):
            pass
        elif normalized.endswith("다"):
            normalized = f"{normalized[:-1]}입니다"
        else:
            normalized = f"{normalized}입니다"

    if not normalized.endswith("."):
        normalized = f"{normalized}."

    if len(normalized) > 120:
        normalized = normalized[:120].rstrip()
        if not normalized.endswith("."):
            normalized = f"{normalized}."

    return normalized


def generate_ai_summary(
    *,
    mode: str,
    card: dict[str, Any],
    candidate: dict[str, Any],
    nickname: str,
) -> str | None:
    payload = _build_prompt_payload(mode=mode, card=card, candidate=candidate, nickname=nickname)
    if not _has_summary_material(payload):
        return None

    prompt = _build_prompt(payload)

    try:
        answer = chat(prompt)
        return _normalize_summary(answer)
    except LLMConfigError:
        logger.info("ai_summary skipped: llm_api_key is not configured")
        return None
    except LLMAuthError:
        logger.warning("ai_summary failed: provider auth error")
        return None
    except LLMRateLimitError:
        logger.warning("ai_summary failed: provider rate limited")
        return None
    except LLMTimeoutError:
        logger.warning("ai_summary failed: provider timeout")
        return None
    except LLMExternalAPIError:
        logger.warning("ai_summary failed: external provider error")
        return None
    except Exception:
        logger.exception("ai_summary failed: unexpected error")
        return None
