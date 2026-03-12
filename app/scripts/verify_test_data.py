from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import inspect, select

from app.db.base import Base
from app.db.migrations import apply_startup_migrations
from app.db.session import SessionLocal, engine
from app.models.matching import MatchingProfile
from app.models.team import Team, TeamInvite, TeamMember
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
        TeamInvite.__table__.create(bind=engine, checkfirst=True)


def run(args: argparse.Namespace) -> int:
    _prepare_schema()
    db = SessionLocal()
    try:
        users = db.scalars(select(User).where(User.user_id.like(f"{args.prefix}%")).order_by(User.user_id.asc())).all()
        user_ids = [user.id for user in users]
        profiles = (
            db.scalars(select(MatchingProfile).where(MatchingProfile.user_id.in_(user_ids))).all()
            if user_ids
            else []
        )
        teams = db.scalars(select(Team).where(Team.team_name.like(f"{args.prefix}%")).order_by(Team.id.asc())).all()
        team_ids = [team.id for team in teams]
        team_members = (
            db.scalars(select(TeamMember).where(TeamMember.team_id.in_(team_ids))).all()
            if team_ids
            else []
        )
        team_profiles = (
            db.scalars(select(TeamMatchingProfile).where(TeamMatchingProfile.team_id.in_(team_ids))).all()
            if team_ids
            else []
        )
        teams_with_recruit_needs = sum(1 for item in team_profiles if item.recruit_needs)
        users_with_team = len({member.user_id for member in team_members})

        print(
            json.dumps(
                {
                    "prefix": args.prefix,
                    "database_url": str(engine.url),
                    "counts": {
                        "test_users": len(users),
                        "onboarding_profiles": len(profiles),
                        "teams": len(teams),
                        "team_memberships": len(team_members),
                        "users_with_team": users_with_team,
                        "standalone_users": max(len(users) - users_with_team, 0),
                        "team_profiles": len(team_profiles),
                        "teams_with_recruit_needs": teams_with_recruit_needs,
                    },
                    "samples": {
                        "user_ids": _sample([user.user_id for user in users]),
                        "team_names": _sample([team.team_name for team in teams]),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        db.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify seeded prefixed test data counts.")
    parser.add_argument("--prefix", type=str, required=True, help="Distinct prefix for test data, e.g. t20260311.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
