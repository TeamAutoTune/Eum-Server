from pydantic import BaseModel, Field


class LLMChatRequest(BaseModel):
    message: str = Field(default="", max_length=4000)


class LLMChatResponse(BaseModel):
    success: bool
    answer: str | None = None
    error_code: str | None = None
    message: str | None = None


class LLMTestSummaryRequest(BaseModel):
    instruments: list[str] = Field(default_factory=list)
    parts: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    region: str = Field(default="")
    availability: list[str] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "instruments": ["보컬"],
                "parts": ["메인보컬"],
                "genres": ["인디", "록"],
                "region": "서울",
                "availability": ["주 1~2회"],
            }
        }
    }


class LLMTestSummaryResponse(BaseModel):
    success: bool
    summary: str | None = None
    error_code: str | None = None
    message: str | None = None
