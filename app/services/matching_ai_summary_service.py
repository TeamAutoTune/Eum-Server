from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
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


def _extract_activity_goal_text(value: Any) -> str:
    if isinstance(value, dict):
        goals = _safe_list(value.get("activityGoals"))
        return ", ".join(goals)
    if isinstance(value, list):
        goals = _safe_list(value)
        return ", ".join(goals)
    return _safe_text(value)


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
        joined = " ".join([piece for piece in [instrument, part] if piece])
        if joined:
            parts.append(joined)
    return parts


def _profile_summary_payload(profile_data: dict[str, Any], candidate_data: dict[str, Any]) -> dict[str, Any]:
    merged = {**(profile_data or {}), **(candidate_data or {})}
    performance_preferences = merged.get("performancePreferences") if isinstance(merged.get("performancePreferences"), dict) else {}
    activity_goal = merged.get("activityGoal") if isinstance(merged.get("activityGoal"), dict) else {}

    payload = {
        "instruments": _safe_list(merged.get("instruments") or merged.get("playableInstruments")),
        "parts": _safe_list(merged.get("parts") or merged.get("primaryParts")),
        "genres": _safe_list(merged.get("genres") or merged.get("preferredGenres")),
        "style": _safe_text(merged.get("style") or performance_preferences.get("performanceStyle")),
        "region": _safe_text(merged.get("region") or performance_preferences.get("activityRegion")),
        "availability": _safe_list(merged.get("availability") or merged.get("availableTimes") or performance_preferences.get("availableTimeSlots")),
        "practiceFrequency": _safe_text(merged.get("practiceFrequency") or performance_preferences.get("practiceFrequency")),
        "activityGoal": _extract_activity_goal_text(activity_goal or merged.get("goals") or merged.get("activityGoals")),
    }
    return {key: value for key, value in payload.items() if value not in ("", [], None)}


def _team_recruit_summary_payload(profile_data: dict[str, Any], recruit_needs: list[dict[str, Any]]) -> dict[str, Any]:
    team_profile = profile_data.get("teamProfile") if isinstance(profile_data.get("teamProfile"), dict) else {}
    merged = {**(profile_data or {}), **team_profile}
    activity_goal = merged.get("activityGoal") if isinstance(merged.get("activityGoal"), dict) else {}

    payload = {
        "teamName": _safe_text(merged.get("teamName")),
        "genres": _safe_list(merged.get("genres")),
        "region": _safe_text(merged.get("region")),
        "practiceFrequency": _safe_text(merged.get("practiceFrequency")),
        "activityGoal": _extract_activity_goal_text(activity_goal or merged.get("goals") or merged.get("activityGoals")),
        "recruitNeeds": _extract_recruiting_parts({"recruitNeeds": recruit_needs}),
    }
    return {key: value for key, value in payload.items() if value not in ("", [], None)}


def _has_summary_material(payload: dict[str, Any]) -> bool:
    return any(payload.values())


def _build_prompt(payload: dict[str, Any], *, subject: str) -> str:
    return (
        f"아래 {subject} JSON 데이터만 사용해 한 줄 소개문을 작성하세요.\n"
        "규칙:\n"
        "1) 반드시 한국어 1문장으로 작성\n"
        "2) 길이는 50~80자 내외\n"
        "3) 과장/광고 문구 금지\n"
        "4) 입력 데이터에 없는 사실 추측 금지\n"
        "5) 자연스러운 소개 문장, '입니다' 체 사용\n"
        "6) 결과는 문장 하나만 출력\n\n"
        f"입력 JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _normalize_summary(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.strip()).strip("\"' ")
    if not normalized:
        return None

    if "\n" in normalized:
        normalized = normalized.splitlines()[0].strip()

    normalized = normalized.rstrip(".!? ")
    if not normalized:
        return None

    if not normalized.endswith("입니다"):
        if normalized.endswith("다"):
            normalized = f"{normalized[:-1]}입니다"
        else:
            normalized = f"{normalized}입니다"

    normalized = f"{normalized}."

    if len(normalized) > 120:
        normalized = normalized[:120].rstrip(" .") + "."

    return normalized


def _generate_summary(prompt: str) -> str | None:
    gemini_api_key = (settings.gemini_api_key or "").strip()
    llm_api_key = (settings.llm_api_key or "").strip()

    if not gemini_api_key:
        logger.info("summary generation: GEMINI_API_KEY is not configured")

    try:
        if llm_api_key:
            answer = chat(prompt)
            summary = _normalize_summary(answer)
            if not summary:
                logger.warning("summary generation failed: empty normalized response")
            return summary

        logger.info("summary generation skipped: no server LLM API key is configured")
        return None
    except LLMConfigError:
        logger.info("summary generation skipped: llm_api_key is not configured")
        return None
    except LLMAuthError:
        logger.warning("summary generation failed: provider auth error")
        return None
    except LLMRateLimitError:
        logger.warning("summary generation failed: provider rate limited")
        return None
    except LLMTimeoutError:
        logger.warning("summary generation failed: provider timeout")
        return None
    except LLMExternalAPIError:
        logger.warning("summary generation failed: external provider error")
        return None
    except Exception:
        logger.exception("summary generation failed: unexpected error")
        return None


def generate_profile_summary(*, profile_data: dict[str, Any], candidate_data: dict[str, Any]) -> str | None:
    payload = _profile_summary_payload(profile_data=profile_data or {}, candidate_data=candidate_data or {})
    if not _has_summary_material(payload):
        return None
    return _generate_summary(_build_prompt(payload, subject="개인 프로필"))


def generate_team_recruit_summary(*, profile_data: dict[str, Any], recruit_needs: list[dict[str, Any]]) -> str | None:
    payload = _team_recruit_summary_payload(profile_data=profile_data or {}, recruit_needs=recruit_needs or [])
    if not _has_summary_material(payload):
        return None
    return _generate_summary(_build_prompt(payload, subject="팀 구인"))
