from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.chat import (
    ChatRoomOut,
    ChatUserOut,
    CreateDirectRoomRequest,
    MessageCreateRequest,
    MessageOut,
)
from app.services import chat_service

router = APIRouter()


def room_to_schema(db: Session, room) -> ChatRoomOut:
    return ChatRoomOut(
        id=room.id,
        room_type=room.room_type,
        created_at=room.created_at,
        member_ids=chat_service._member_ids(db, room.id),
    )


@router.post("/rooms/direct", response_model=ChatRoomOut)
def create_direct_room(
    payload: CreateDirectRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = chat_service.create_or_get_direct_room(db, current_user.id, payload.target_user_id)
    return room_to_schema(db, room)


@router.get("/rooms", response_model=list[ChatRoomOut])
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rooms = chat_service.list_my_rooms(db, current_user.id)
    return [room_to_schema(db, room) for room in rooms]


@router.get("/users", response_model=list[ChatUserOut])
def list_chat_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    users = chat_service.list_chat_candidates(db, current_user.id)
    return [
        ChatUserOut(
            id=user.id,
            nickname=user.nickname,
            user_id=user.user_id,
            instrument=user.instrument,
        )
        for user in users
    ]


@router.get("/rooms/{room_id}/messages", response_model=list[MessageOut])
def list_messages(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_service.ensure_member(db, room_id, current_user.id)
    return chat_service.list_room_messages(db, room_id)


@router.post("/rooms/{room_id}/messages", response_model=MessageOut)
def send_message(
    room_id: str,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_service.ensure_member(db, room_id, current_user.id)
    return chat_service.create_message(db, room_id, current_user.id, payload.content)
