from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, inspect, select

from app.core.security import hash_password
from app.db.base import Base
from app.db.migrations import apply_startup_migrations
from app.db.session import SessionLocal, engine
from app.models.matching import MatchingProfile
from app.models.team import Team, TeamInvite, TeamMember
from app.models.team_matching_profile import TeamMatchingProfile
from app.models.user import User
from app.scripts.test_data_support import (
    build_export_path,
    build_nickname,
    build_team_name,
    build_user_id,
    generate_team_seed,
    generate_user_profile,
    write_csv_export,
    write_json_export,
)
from app.core.security import verify_password


def _set_attrs_if_changed(instance, values: dict) -> bool:
    changed = False
    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed = True
    return changed


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
        TeamInvite.__table__.create(bind=engine, checkfirst=True)


def run(args: argparse.Namespace) -> int:
    if args.teams > args.users:
        raise ValueError("--teams cannot exceed --users")

    rng_seed = args.seed if args.seed is not None else 42
    from random import Random

    rng = Random(rng_seed)
    _prepare_schema()

    password_hash = hash_password(args.password)
    export_rows: list[dict] = []
    report = {
        "users_created": 0,
        "users_updated": 0,
        "users_skipped": 0,
        "profiles_created": 0,
        "profiles_updated": 0,
        "profiles_skipped": 0,
        "teams_created": 0,
        "teams_updated": 0,
        "teams_skipped": 0,
        "team_profiles_created": 0,
        "team_profiles_updated": 0,
        "team_profiles_skipped": 0,
        "team_memberships_reset": 0,
        "failed": 0,
    }
    samples = {
        "user_ids": [],
        "team_names": [],
        "team_ids": [],
    }

    db = SessionLocal()
    transaction = db.begin()
    try:
        users: list[User] = []
        team_id_by_user_id: dict[str, int | None] = {}
        leader_user_ids: set[str] = set()

        for index in range(1, args.users + 1):
            user_id = build_user_id(args.prefix, index)
            nickname = build_nickname(args.prefix, index)
            profile_data, candidate_data = generate_user_profile(
                args.prefix,
                index,
                rng,
                force_sido=args.force_sido,
            )
            instrument = candidate_data["instruments"][0]

            user = db.scalar(select(User).where(User.user_id == user_id))
            if not user:
                user = User(
                    nickname=nickname,
                    user_id=user_id,
                    hashed_password=password_hash,
                    instrument=instrument,
                )
                db.add(user)
                db.flush()
                report["users_created"] += 1
            else:
                user_updates = {
                    "nickname": nickname,
                    "instrument": instrument,
                }
                if not verify_password(args.password, user.hashed_password):
                    user_updates["hashed_password"] = password_hash
                changed = _set_attrs_if_changed(user, user_updates)
                report["users_updated" if changed else "users_skipped"] += 1

            profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
            if not profile:
                db.add(
                    MatchingProfile(
                        user_id=user.id,
                        profile_data=profile_data,
                        candidate_data=candidate_data,
                    )
                )
                report["profiles_created"] += 1
            else:
                changed = _set_attrs_if_changed(
                    profile,
                    {
                        "profile_data": profile_data,
                        "candidate_data": candidate_data,
                    },
                )
                report["profiles_updated" if changed else "profiles_skipped"] += 1

            users.append(user)
            team_id_by_user_id[user.id] = None
            export_rows.append(
                {
                    "user_id": user.user_id,
                    "nickname": user.nickname,
                    "is_leader": False,
                    "team_id": "",
                }
            )

        leaders = users[: args.teams]

        for index, leader in enumerate(leaders, start=1):
            leader_user_ids.add(leader.id)
            team_name = build_team_name(args.prefix, index)
            team_fields, team_profile_data, recruit_needs, _ = generate_team_seed(
                args.prefix,
                index,
                rng,
                force_sido=args.force_sido,
            )
            team = db.scalar(select(Team).where(Team.team_name == team_name))

            field_payload = {
                "team_name": team_fields["team_name"],
                "description": team_fields["description"],
                "average_age": team_fields["average_age"],
                "region": team_fields["region"],
                "genres": json.dumps(team_fields["genres"], ensure_ascii=False),
                "gender_ratio": team_fields["gender_ratio"],
                "reference_songs": json.dumps(team_fields["reference_songs"], ensure_ascii=False),
                "leader_id": leader.id,
            }

            if not team:
                team = Team(**field_payload)
                db.add(team)
                db.flush()
                report["teams_created"] += 1
            else:
                changed = _set_attrs_if_changed(team, field_payload)
                report["teams_updated" if changed else "teams_skipped"] += 1

            db.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
            db.add(TeamMember(team_id=team.id, user_id=leader.id, role="leader"))
            team_id_by_user_id[leader.id] = team.id
            report["team_memberships_reset"] += 1

            team_profile = db.scalar(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id == team.id))
            if not team_profile:
                db.add(
                    TeamMatchingProfile(
                        team_id=team.id,
                        profile_data=team_profile_data,
                        recruit_needs=recruit_needs,
                    )
                )
                report["team_profiles_created"] += 1
            else:
                changed = _set_attrs_if_changed(
                    team_profile,
                    {
                        "profile_data": team_profile_data,
                        "recruit_needs": recruit_needs,
                    },
                )
                report["team_profiles_updated" if changed else "team_profiles_skipped"] += 1

            samples["team_names"].append(team.team_name)
            samples["team_ids"].append(str(team.id))

        for row in export_rows:
            user = db.scalar(select(User).where(User.user_id == row["user_id"]))
            if not user:
                continue
            row["is_leader"] = user.id in leader_user_ids
            row["team_id"] = "" if team_id_by_user_id[user.id] is None else str(team_id_by_user_id[user.id])

        if args.export_json:
            write_json_export(build_export_path(args.prefix, args.output_dir, "json"), export_rows)
        if args.export_csv:
            write_csv_export(build_export_path(args.prefix, args.output_dir, "csv"), export_rows)

        samples["user_ids"] = [row["user_id"] for row in export_rows]
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
                "seed": rng_seed,
                "database_url": str(engine.url),
                "report": report,
                "samples": {
                    "user_ids": _sample(samples["user_ids"]),
                    "team_names": _sample(samples["team_names"]),
                    "team_ids": _sample(samples["team_ids"]),
                },
                "exports": {
                    "json": str(build_export_path(args.prefix, args.output_dir, "json")) if args.export_json else None,
                    "csv": str(build_export_path(args.prefix, args.output_dir, "csv")) if args.export_csv else None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed prefixed test users, profiles, teams, and recruit needs.")
    parser.add_argument("--users", type=int, default=200, help="Number of test users to create.")
    parser.add_argument("--teams", type=int, default=50, help="Number of teams to create from the first N users.")
    parser.add_argument("--prefix", type=str, required=True, help="Distinct prefix for test data, e.g. t20260311.")
    parser.add_argument("--password", type=str, default="seed1234", help="Shared password for seeded test users.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible data.")
    parser.add_argument(
        "--force-sido",
        type=str,
        default=None,
        help="Force all seeded regions to one sido, e.g. 서울특별시.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build and validate data, then roll back.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path("logs") / "test_data_exports"),
        help="Directory for JSON/CSV exports.",
    )
    parser.add_argument("--export-json", action="store_true", help="Export seeded account summary as JSON.")
    parser.add_argument("--export-csv", action="store_true", help="Export seeded account summary as CSV.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
