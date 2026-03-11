from typing import Any

from fastapi import APIRouter, Body
from pydantic import ValidationError

from app.schemas.llm import LLMChatRequest, LLMChatResponse
from app.services.llm_service import (
    LLMAuthError,
    LLMConfigError,
    LLMExternalAPIError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
    chat,
)

router = APIRouter()


@router.post("/chat", response_model=LLMChatResponse)
def llm_chat(raw_payload: dict[str, Any] = Body(...)):
    try:
        payload = LLMChatRequest.model_validate(raw_payload)
    except ValidationError:
        return LLMChatResponse(
            success=False,
            answer=None,
            error_code="INVALID_REQUEST",
            message="Invalid request body.",
        )

    message = payload.message.strip()
    if not message:
        return LLMChatResponse(
            success=False,
            answer=None,
            error_code="INVALID_INPUT",
            message="message must not be empty.",
        )

    try:
        answer = chat(message)
        return LLMChatResponse(success=True, answer=answer, error_code=None, message=None)
    except (LLMConfigError, LLMAuthError, LLMRateLimitError, LLMTimeoutError, LLMExternalAPIError) as exc:
        return LLMChatResponse(success=False, answer=None, error_code=exc.error_code, message=exc.message)
    except LLMServiceError as exc:
        return LLMChatResponse(success=False, answer=None, error_code=exc.error_code, message=exc.message)
    except Exception:
        return LLMChatResponse(
            success=False,
            answer=None,
            error_code="INTERNAL_ERROR",
            message="Unexpected server error occurred.",
        )
