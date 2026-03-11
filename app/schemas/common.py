from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nickname: str
    user_id: str
    instrument: str
    gender: str | None = None
    age: int | None = None
    created_at: datetime
