import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class LLMConfigError(LLMServiceError):
    pass


class LLMAuthError(LLMServiceError):
    pass


class LLMRateLimitError(LLMServiceError):
    pass


class LLMTimeoutError(LLMServiceError):
    pass


class LLMExternalAPIError(LLMServiceError):
    pass


def _build_timeout() -> httpx.Timeout:
    timeout = max(settings.llm_timeout_seconds, 1.0)
    return httpx.Timeout(timeout=timeout)


def _provider_error_message(response: httpx.Response, default_message: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return default_message

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    if isinstance(payload.get("message"), str) and payload["message"].strip():
        return payload["message"].strip()
    return default_message


def chat(message: str) -> str:
    api_key = (settings.llm_api_key or "").strip()
    if not api_key:
        raise LLMConfigError(
            error_code="SERVER_CONFIG_ERROR",
            message="LLM API key is not configured on the server.",
        )

    base_url = settings.llm_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.3,
    }

    attempts = max(settings.llm_max_retries, 0) + 1
    backoff_seconds = 0.4

    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=_build_timeout()) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            if attempt < attempts:
                time.sleep(backoff_seconds)
                continue
            raise LLMTimeoutError(
                error_code="TIMEOUT",
                message="LLM response timed out. Please try again shortly.",
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("LLM request failed due to network/client error: %s", exc.__class__.__name__)
            if attempt < attempts:
                time.sleep(backoff_seconds)
                continue
            raise LLMExternalAPIError(
                error_code="EXTERNAL_API_ERROR",
                message="External LLM service is currently unavailable.",
            ) from exc

        if response.status_code == 401:
            raise LLMAuthError(
                error_code="AUTH_ERROR",
                message="LLM authentication failed on the server.",
            )
        if response.status_code == 429:
            raise LLMRateLimitError(
                error_code="RATE_LIMIT",
                message="Too many requests. Please try again later.",
            )
        if response.status_code >= 500:
            logger.warning("LLM provider server error status: %s", response.status_code)
            if attempt < attempts:
                time.sleep(backoff_seconds)
                continue
            raise LLMExternalAPIError(
                error_code="EXTERNAL_API_ERROR",
                message="External LLM service returned a server error.",
            )
        if response.status_code >= 400:
            message = _provider_error_message(response, "LLM request was rejected.")
            raise LLMExternalAPIError(
                error_code="EXTERNAL_API_ERROR",
                message=message,
            )

        try:
            response_data = response.json()
            answer = response_data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("LLM response parsing failed")
            raise LLMExternalAPIError(
                error_code="EXTERNAL_API_ERROR",
                message="Invalid response received from external LLM service.",
            ) from exc

        if not isinstance(answer, str) or not answer.strip():
            raise LLMExternalAPIError(
                error_code="EXTERNAL_API_ERROR",
                message="LLM returned an empty response.",
            )

        return answer.strip()

    raise LLMExternalAPIError(
        error_code="EXTERNAL_API_ERROR",
        message="External LLM service is currently unavailable.",
    )
