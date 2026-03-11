from pydantic import BaseModel, Field


class LLMChatRequest(BaseModel):
    message: str = Field(default="", max_length=4000)


class LLMChatResponse(BaseModel):
    success: bool
    answer: str | None = None
    error_code: str | None = None
    message: str | None = None
