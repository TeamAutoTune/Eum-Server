from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateDirectRoomRequest(BaseModel):
    target_user_id: str


class RoomMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str


class ChatRoomOut(BaseModel):
    id: str
    room_type: str
    created_at: datetime
    member_ids: list[str]


class ChatUserOut(BaseModel):
    id: str
    nickname: str
    user_id: str
    instrument: str


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: str
    room_id: str
    sender_id: str
    content: str
    created_at: datetime
