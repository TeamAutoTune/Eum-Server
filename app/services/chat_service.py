from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.chat import ChatRoom, ChatRoomMember, Message
from app.models.matching import MatchingProfile
from app.models.user import User


def _member_ids(db: Session, room_id: str) -> list[str]:
    rows = db.scalars(select(ChatRoomMember.user_id).where(ChatRoomMember.room_id == room_id)).all()
    return list(rows)


def create_or_get_direct_room(db: Session, me_id: str, target_user_id: str) -> ChatRoom:
    if me_id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create direct room with yourself")

    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    my_room_ids = db.scalars(select(ChatRoomMember.room_id).where(ChatRoomMember.user_id == me_id)).all()

    for room_id in my_room_ids:
        room = db.get(ChatRoom, room_id)
        if not room or room.room_type != "direct":
            continue

        members = set(_member_ids(db, room_id))
        if members == {me_id, target_user_id}:
            return room

    room = ChatRoom(room_type="direct")
    db.add(room)
    db.flush()

    db.add(ChatRoomMember(room_id=room.id, user_id=me_id))
    db.add(ChatRoomMember(room_id=room.id, user_id=target_user_id))
    db.commit()
    db.refresh(room)
    return room


def list_my_rooms(db: Session, me_id: str) -> list[ChatRoom]:
    room_ids = db.scalars(select(ChatRoomMember.room_id).where(ChatRoomMember.user_id == me_id)).all()
    if not room_ids:
        return []
    return db.scalars(select(ChatRoom).where(ChatRoom.id.in_(room_ids))).all()


def ensure_member(db: Session, room_id: str, user_id: str) -> None:
    membership = db.scalar(
        select(ChatRoomMember).where(
            and_(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id)
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a room member")


def list_room_messages(db: Session, room_id: str) -> list[Message]:
    return db.scalars(select(Message).where(Message.room_id == room_id).order_by(Message.created_at.asc())).all()


def create_message(db: Session, room_id: str, sender_id: str, content: str) -> Message:
    room = db.get(ChatRoom, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    message = Message(room_id=room_id, sender_id=sender_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_chat_candidates(db: Session, me_id: str) -> list[User]:
    # Unify eligibility with matching: only users with onboarding profile are chat candidates.
    return db.scalars(
        select(User)
        .join(MatchingProfile, MatchingProfile.user_id == User.id)
        .where(User.id != me_id)
        .order_by(User.created_at.desc())
    ).all()


def list_chat_candidate_profiles(db: Session, me_id: str) -> list[tuple[User, MatchingProfile]]:
    return db.execute(
        select(User, MatchingProfile)
        .join(MatchingProfile, MatchingProfile.user_id == User.id)
        .where(User.id != me_id)
        .order_by(User.created_at.desc())
    ).all()
