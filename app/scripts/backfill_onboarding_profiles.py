from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import inspect, select

from app.db.base import Base
from app.db.migrations import apply_startup_migrations
from app.db.session import SessionLocal, engine
from app.models.matching import MatchingProfile
from app.models.team import Team
from app.models.team_matching_profile import TeamMatchingProfile
from app.models.user import User
from app.schemas.onboarding import PersonalOnboardingUpsertRequest, TeamOnboardingUpsertRequest
from app.services.onboarding_service import upsert_personal_onboarding, upsert_team_onboarding


def _prepare_schema() -> None:
    apply_startup_migrations(engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        Base.metadata.create_all(bind=engine)
    else:
        MatchingProfile.__table__.create(bind=engine, checkfirst=True)
        TeamMatchingProfile.__table__.create(bind=engine, checkfirst=True)


def _sample(values: list[str], limit: int = 5) -> list[str]:
    return values[:limit]


def run(args: argparse.Namespace) -> int:
    _prepare_schema()
    db = SessionLocal()
    report = {
        "users_seen": 0,
        "users_backfilled": 0,
        "users_skipped_no_profile": 0,
        "teams_seen": 0,
        "teams_backfilled": 0,
        "teams_created_minimal_profile": 0,
        "failed": 0,
    }
    samples = {
        "users_backfilled": [],
        "users_skipped_no_profile": [],
        "teams_backfilled": [],
    }

    transaction = db.begin()
    try:
        users_query = select(User).order_by(User.created_at.asc())
        if args.user_id_prefix:
            users_query = users_query.where(User.user_id.like(f"{args.user_id_prefix}%"))
        users = db.scalars(users_query).all()

        for user in users:
            report["users_seen"] += 1
            existing_profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
            if not existing_profile:
                report["users_skipped_no_profile"] += 1
                samples["users_skipped_no_profile"].append(user.user_id)
                continue

            payload = PersonalOnboardingUpsertRequest(
                profile_data=existing_profile.profile_data or {},
                candidate_data=existing_profile.candidate_data or {},
            )
            upsert_personal_onboarding(db, user, payload, auto_commit=False)
            report["users_backfilled"] += 1
            samples["users_backfilled"].append(user.user_id)

        teams_query = select(Team).order_by(Team.created_at.asc())
        if args.team_name_prefix:
            teams_query = teams_query.where(Team.team_name.like(f"{args.team_name_prefix}%"))
        teams = db.scalars(teams_query).all()

        for team in teams:
            report["teams_seen"] += 1
            team_profile = db.scalar(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id == team.id))
            if team_profile:
                payload = TeamOnboardingUpsertRequest(
                    profile_data=team_profile.profile_data or {},
                    recruit_needs=team_profile.recruit_needs or [],
                )
            else:
                payload = TeamOnboardingUpsertRequest(
                    profile_data={
                        "teamProfile": {
                            "teamName": team.team_name,
                            "region": team.region,
                            "averageAge": team.average_age,
                        },
                    },
                    recruit_needs=[],
                )
                report["teams_created_minimal_profile"] += 1

            leader = db.get(User, team.leader_id)
            if not leader:
                continue
            upsert_team_onboarding(
                db,
                team_id=team.id,
                current_user=leader,
                payload=payload,
                auto_commit=False,
            )
            report["teams_backfilled"] += 1
            samples["teams_backfilled"].append(team.team_name)

        if args.dry_run:
            transaction.rollback()
        else:
            transaction.commit()

        print(
            json.dumps(
                {
                    "database_url": str(engine.url),
                    "dry_run": args.dry_run,
                    "filters": {
                        "user_id_prefix": args.user_id_prefix,
                        "team_name_prefix": args.team_name_prefix,
                    },
                    "report": report,
                    "samples": {
                        "users_backfilled": _sample(samples["users_backfilled"]),
                        "users_skipped_no_profile": _sample(samples["users_skipped_no_profile"]),
                        "teams_backfilled": _sample(samples["teams_backfilled"]),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception:
        report["failed"] += 1
        transaction.rollback()
        raise
    finally:
        db.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill legacy onboarding rows into the new normalized onboarding storage flow.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without committing changes.")
    parser.add_argument("--user-id-prefix", type=str, default="", help="Only process users whose user_id starts with this prefix.")
    parser.add_argument("--team-name-prefix", type=str, default="", help="Only process teams whose team_name starts with this prefix.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
