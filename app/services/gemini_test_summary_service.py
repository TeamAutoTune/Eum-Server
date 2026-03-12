from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    settings_api_key = (settings.gemini_api_key or "").strip()
    env_api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    api_key = settings_api_key or env_api_key

    logger.info(
        "gemini summary env check: GEMINI_API_KEY exists(os.getenv)=%s, settings.gemini_api_key exists=%s",
        bool(env_api_key),
        bool(settings_api_key),
    )

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
        from google.genai import errors as genai_errors
        from google.genai import types
    except Exception as exc:
        raise GeminiConfigError("GEMINI_SDK_MISSING", "Gemini SDK is not installed on the server.") from exc

    try:
        http_options = types.HttpOptions(
            # Local/dev environments often export blocking proxy values.
            # Defaulting to direct connection avoids false GEMINI_CALL_FAILED.
            client_args={"trust_env": settings.gemini_use_env_proxy},
            async_client_args={"trust_env": settings.gemini_use_env_proxy},
        )
        client = genai.Client(api_key=api_key, http_options=http_options)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
    except genai_errors.ClientError as exc:
        detail = str(exc)
        if "PERMISSION_DENIED" in detail or "API key" in detail:
            raise GeminiConfigError(
                "GEMINI_AUTH_ERROR",
                "Gemini API key is invalid, revoked, or blocked.",
            ) from exc
        if "RESOURCE_EXHAUSTED" in detail or "429" in detail:
            raise GeminiCallError("GEMINI_RATE_LIMIT", "Gemini API rate limit exceeded.") from exc
        raise GeminiCallError("GEMINI_CALL_FAILED", "Failed to call Gemini API.") from exc
    except Exception as exc:
        raise GeminiCallError("GEMINI_NETWORK_ERROR", f"Failed to call Gemini API: {exc}") from exc

    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise GeminiEmptyResponseError("EMPTY_RESPONSE", "Gemini returned an empty response.")

    summary = _normalize_summary(text)
    if not summary:
        raise GeminiEmptyResponseError("EMPTY_RESPONSE", "Gemini returned an empty response.")

    return summary
