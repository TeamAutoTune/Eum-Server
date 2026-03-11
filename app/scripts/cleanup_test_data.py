from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import delete, inspect, select

from app.db.base import Base
from app.db.migrations import apply_startup_migrations
from app.db.session import SessionLocal, engine
from app.models.chat import ChatRoom, ChatRoomMember, Message
from app.models.matching import MatchingProfile
from app.models.team import Team, TeamChecklist, TeamMember, TeamNotice, TeamSchedule
from app.models.team_matching_profile import TeamMatchingProfile
from app.models.user import User


def _sample(values: list[str], limit: int = 5) -> list[str]:
    return values[:limit]


def _prepare_schema() -> None:
    apply_startup_migrations(engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        Base.metadata.create_all(bind=engine)
    else:
        TeamMatchingProfile.__table__.create(bind=engine, checkfirst=True)


def run(args: argparse.Namespace) -> int:
    _prepare_schema()
    db = SessionLocal()
    transaction = db.begin()
    report = {
        "users_deleted": 0,
        "profiles_deleted": 0,
        "teams_deleted": 0,
        "team_profiles_deleted": 0,
        "team_members_deleted": 0,
        "team_notices_deleted": 0,
        "team_checklists_deleted": 0,
        "team_schedules_deleted": 0,
        "chat_members_deleted": 0,
        "messages_deleted": 0,
        "chat_rooms_deleted": 0,
        "failed": 0,
    }
    samples = {"user_ids": [], "team_names": []}

    try:
        prefixed_users = db.scalars(select(User).where(User.user_id.like(f"{args.prefix}%"))).all()
        prefixed_user_ids = [user.id for user in prefixed_users]
        samples["user_ids"] = [user.user_id for user in prefixed_users]

        prefixed_teams = db.scalars(select(Team).where(Team.team_name.like(f"{args.prefix}%"))).all()
        prefixed_team_ids = [team.id for team in prefixed_teams]
        samples["team_names"] = [team.team_name for team in prefixed_teams]

        if prefixed_team_ids:
            report["team_profiles_deleted"] = db.execute(
                delete(TeamMatchingProfile).where(TeamMatchingProfile.team_id.in_(prefixed_team_ids))
            ).rowcount or 0
            report["team_notices_deleted"] = db.execute(
                delete(TeamNotice).where(TeamNotice.team_id.in_(prefixed_team_ids))
            ).rowcount or 0
            report["team_checklists_deleted"] = db.execute(
                delete(TeamChecklist).where(TeamChecklist.team_id.in_(prefixed_team_ids))
            ).rowcount or 0
            report["team_schedules_deleted"] = db.execute(
                delete(TeamSchedule).where(TeamSchedule.team_id.in_(prefixed_team_ids))
            ).rowcount or 0
            report["team_members_deleted"] += db.execute(
                delete(TeamMember).where(TeamMember.team_id.in_(prefixed_team_ids))
            ).rowcount or 0
            report["teams_deleted"] = db.execute(delete(Team).where(Team.id.in_(prefixed_team_ids))).rowcount or 0

        if prefixed_user_ids:
            member_room_ids = db.scalars(
                select(ChatRoomMember.room_id).where(ChatRoomMember.user_id.in_(prefixed_user_ids))
            ).all()
            report["chat_members_deleted"] = db.execute(
                delete(ChatRoomMember).where(ChatRoomMember.user_id.in_(prefixed_user_ids))
            ).rowcount or 0
            report["messages_deleted"] = db.execute(
                delete(Message).where(Message.sender_id.in_(prefixed_user_ids))
            ).rowcount or 0
            report["team_members_deleted"] += db.execute(
                delete(TeamMember).where(TeamMember.user_id.in_(prefixed_user_ids))
            ).rowcount or 0
            report["profiles_deleted"] = db.execute(
                delete(MatchingProfile).where(MatchingProfile.user_id.in_(prefixed_user_ids))
            ).rowcount or 0
            report["users_deleted"] = db.execute(delete(User).where(User.id.in_(prefixed_user_ids))).rowcount or 0

            if member_room_ids:
                orphan_rooms = []
                for room_id in set(member_room_ids):
                    remaining = db.scalar(
                        select(ChatRoomMember.id).where(ChatRoomMember.room_id == room_id).limit(1)
                    )
                    if remaining is None:
                        orphan_rooms.append(room_id)
                if orphan_rooms:
                    db.execute(delete(Message).where(Message.room_id.in_(orphan_rooms)))
                    report["chat_rooms_deleted"] = db.execute(
                        delete(ChatRoom).where(ChatRoom.id.in_(orphan_rooms))
                    ).rowcount or 0

        if args.dry_run:
            transaction.rollback()
        else:
            transaction.commit()
    except Exception:
        report["failed"] += 1
        transaction.rollback()
        raise
    finally:
        db.close()

    print(
        json.dumps(
            {
                "prefix": args.prefix,
                "dry_run": args.dry_run,
                "database_url": str(engine.url),
                "report": report,
                "samples": {
                    "user_ids": _sample(samples["user_ids"]),
                    "team_names": _sample(samples["team_names"]),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete prefixed test users, profiles, and teams.")
    parser.add_argument("--prefix", type=str, required=True, help="Distinct prefix for test data, e.g. t20260311.")
    parser.add_argument("--dry-run", action="store_true", help="Compute deletion targets, then roll back.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
