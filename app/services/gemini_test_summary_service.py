from __future__ import annotations

import re
from typing import Any

from app.core.config import settings


class GeminiTestSummaryError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class GeminiConfigError(GeminiTestSummaryError):
    pass


class GeminiInputError(GeminiTestSummaryError):
    pass


class GeminiCallError(GeminiTestSummaryError):
    pass


class GeminiEmptyResponseError(GeminiTestSummaryError):
    pass


def _normalize_list(items: list[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _is_empty_payload(payload: dict[str, Any]) -> bool:
    return not any(
        [
            payload["instruments"],
            payload["parts"],
            payload["genres"],
            payload["region"],
            payload["availability"],
        ]
    )


def _build_prompt(payload: dict[str, Any]) -> str:
    return (
        "아래 프로필 정보만 사용해 한국어 소개 문장 1개를 작성해주세요.\n"
        "규칙:\n"
        "1) 반드시 한국어 1문장\n"
        "2) 50~80자 내외\n"
        "3) 과장 금지\n"
        "4) 입력에 없는 정보 추측 금지\n"
        "5) 반드시 '입니다'체\n"
        "6) 결과는 문장만 출력\n\n"
        f"프로필 정보: {payload}"
    )


def _normalize_summary(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.strip()).strip("\"' ")
    if not normalized:
        return None

    if "\n" in normalized:
        normalized = normalized.splitlines()[0].strip()

    sentence_end = re.search(r"[.!?]", normalized)
    if sentence_end:
        normalized = normalized[: sentence_end.start()].strip()

    if normalized.endswith("입니다"):
        normalized = f"{normalized}."
    elif normalized.endswith("."):
        if not normalized.endswith("입니다."):
            normalized = f"{normalized.rstrip('.')}입니다."
    else:
        if normalized.endswith("다"):
            normalized = f"{normalized[:-1]}입니다."
        else:
            normalized = f"{normalized}입니다."

    return normalized if normalized.strip() else None


def generate_test_summary(
    *,
    instruments: list[str],
    parts: list[str],
    genres: list[str],
    region: str,
    availability: list[str],
) -> str:
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise GeminiConfigError("GEMINI_API_KEY_MISSING", "GEMINI_API_KEY is not configured.")

    payload = {
        "instruments": _normalize_list(instruments),
        "parts": _normalize_list(parts),
        "genres": _normalize_list(genres),
        "region": str(region or "").strip(),
        "availability": _normalize_list(availability),
    }
    if _is_empty_payload(payload):
        raise GeminiInputError("INVALID_INPUT", "At least one profile field must be provided.")

    prompt = _build_prompt(payload)

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        raise GeminiConfigError("GEMINI_SDK_MISSING", "Gemini SDK is not installed on the server.") from exc

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
    except Exception as exc:
        raise GeminiCallError("GEMINI_CALL_FAILED", "Failed to call Gemini API.") from exc

    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise GeminiEmptyResponseError("EMPTY_RESPONSE", "Gemini returned an empty response.")

    summary = _normalize_summary(text)
    if not summary:
        raise GeminiEmptyResponseError("EMPTY_RESPONSE", "Gemini returned an empty response.")

    return summary
