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
from app.services.matching_ai_summary_service import (
    generate_profile_summary,
    generate_team_recruit_summary,
)


def _prepare_schema() -> None:
    apply_startup_migrations(engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if not existing_tables:
        Base.metadata.create_all(bind=engine)
    else:
        MatchingProfile.__table__.create(bind=engine, checkfirst=True)
        TeamMatchingProfile.__table__.create(bind=engine, checkfirst=True)


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _sample(values: list[str], limit: int = 5) -> list[str]:
    return values[:limit]


def _refresh_personal_summary(row: MatchingProfile) -> str | None:
    summary = generate_profile_summary(
        profile_data=row.profile_data or {},
        candidate_data=row.candidate_data or {},
    )
    row.profile_summary = summary

    next_candidate_data = _safe_dict(row.candidate_data).copy()
    if summary:
        next_candidate_data["ai_summary"] = summary
    else:
        next_candidate_data.pop("ai_summary", None)
    row.candidate_data = next_candidate_data

    next_profile_data = _safe_dict(row.profile_data).copy()
    if summary:
        next_profile_data["ai_summary"] = summary
    else:
        next_profile_data.pop("ai_summary", None)
    row.profile_data = next_profile_data
    return summary


def _refresh_team_summary(row: TeamMatchingProfile, team_name: str | None = None) -> str | None:
    summary = generate_team_recruit_summary(
        profile_data=row.profile_data or {},
        recruit_needs=row.recruit_needs or [],
    )
    row.recruit_summary = summary

    next_profile_data = _safe_dict(row.profile_data).copy()
    team_profile = _safe_dict(next_profile_data.get("teamProfile")).copy()
    if team_name and not team_profile.get("teamName"):
        team_profile["teamName"] = team_name
    if summary:
        team_profile["ai_summary"] = summary
    else:
        team_profile.pop("ai_summary", None)
    next_profile_data["teamProfile"] = team_profile
    row.profile_data = next_profile_data
    return summary


def run(args: argparse.Namespace) -> int:
    _prepare_schema()
    db = SessionLocal()
    report = {
        "personal_seen": 0,
        "personal_updated": 0,
        "personal_cleared": 0,
        "team_seen": 0,
        "team_updated": 0,
        "team_cleared": 0,
    }
    samples = {
        "personal_updated": [],
        "personal_cleared": [],
        "team_updated": [],
        "team_cleared": [],
    }

    transaction = db.begin()
    try:
        personal_query = (
            select(MatchingProfile, User)
            .join(User, User.id == MatchingProfile.user_id)
            .order_by(User.created_at.asc())
        )
        if args.user_id_prefix:
            personal_query = personal_query.where(User.user_id.like(f"{args.user_id_prefix}%"))
        personal_rows = db.execute(personal_query).all()

        for row, user in personal_rows:
            report["personal_seen"] += 1
            summary = _refresh_personal_summary(row)
            if summary:
                report["personal_updated"] += 1
                samples["personal_updated"].append(user.user_id)
            else:
                report["personal_cleared"] += 1
                samples["personal_cleared"].append(user.user_id)

        team_query = (
            select(TeamMatchingProfile, Team)
            .join(Team, Team.id == TeamMatchingProfile.team_id)
            .order_by(Team.created_at.asc())
        )
        if args.team_name_prefix:
            team_query = team_query.where(Team.team_name.like(f"{args.team_name_prefix}%"))
        team_rows = db.execute(team_query).all()

        for row, team in team_rows:
            report["team_seen"] += 1
            summary = _refresh_team_summary(row, team_name=team.team_name)
            if summary:
                report["team_updated"] += 1
                samples["team_updated"].append(team.team_name)
            else:
                report["team_cleared"] += 1
                samples["team_cleared"].append(team.team_name)

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
                        "personal_updated": _sample(samples["personal_updated"]),
                        "personal_cleared": _sample(samples["personal_cleared"]),
                        "team_updated": _sample(samples["team_updated"]),
                        "team_cleared": _sample(samples["team_cleared"]),
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
    parser = argparse.ArgumentParser(description="Regenerate stored personal/team matching summaries using the current summary generator.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without committing changes.")
    parser.add_argument("--user-id-prefix", type=str, default="", help="Only process users whose user_id starts with this prefix.")
    parser.add_argument("--team-name-prefix", type=str, default="", help="Only process teams whose team_name starts with this prefix.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
