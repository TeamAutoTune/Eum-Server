import argparse
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, board, chat, home, llm, matching, onboarding, team, team_checklist, team_notice, team_schedule
from app.core.config import settings
from app.db.base import Base
from app.db.migrations import apply_startup_migrations
from app.db.session import SessionLocal, engine
from app.scripts.backfill_matching_summaries import run as run_matching_summary_backfill
from app.scripts.backfill_onboarding_profiles import run as run_onboarding_backfill
from app.services import board_service

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(board.router, prefix="/api/board", tags=["board"])
    app.include_router(board.upload_router, prefix="/api", tags=["uploads"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
    app.include_router(home.router, prefix="/api/home", tags=["home"])
    app.include_router(matching.router, prefix="/api/matching", tags=["matching"])
    app.include_router(onboarding.router, prefix="/api/onboarding", tags=["onboarding"])
    app.include_router(team.router, prefix="/api/team", tags=["team"])
    app.include_router(team_notice.router, prefix="/api/team", tags=["team-notice"])
    app.include_router(team_checklist.router, prefix="/api/team", tags=["team-checklist"])
    app.include_router(team_schedule.router, prefix="/api/team", tags=["team-schedule"])

    static_dir = Path(__file__).resolve().parents[1] / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    gemini_env_exists = bool((os.getenv("GEMINI_API_KEY") or "").strip())
    gemini_settings_exists = bool((settings.gemini_api_key or "").strip())
    llm_env_exists = bool((os.getenv("LLM_API_KEY") or "").strip())
    llm_settings_exists = bool((settings.llm_api_key or "").strip())
    logger.info(
        "startup env check: GEMINI_API_KEY exists(os.getenv)=%s settings.gemini_api_key exists=%s LLM_API_KEY exists(os.getenv)=%s settings.llm_api_key exists=%s",
        gemini_env_exists,
        gemini_settings_exists,
        llm_env_exists,
        llm_settings_exists,
    )

    apply_startup_migrations(engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        board_service.seed_board_data(db)
    except Exception:
        logger.exception("Board seed failed during startup")
    finally:
        db.close()

    if settings.backfill_onboarding_on_startup:
        try:
            exit_code = run_onboarding_backfill(
                argparse.Namespace(
                    dry_run=False,
                    user_id_prefix=settings.backfill_onboarding_user_id_prefix,
                    team_name_prefix=settings.backfill_onboarding_team_name_prefix,
                )
            )
            logger.info(
                "Startup onboarding backfill finished exit_code=%s user_id_prefix=%s team_name_prefix=%s",
                exit_code,
                settings.backfill_onboarding_user_id_prefix,
                settings.backfill_onboarding_team_name_prefix,
            )
        except Exception:
            logger.exception("Startup onboarding backfill failed")

    if settings.backfill_matching_summaries_on_startup:
        try:
            exit_code = run_matching_summary_backfill(
                argparse.Namespace(
                    dry_run=False,
                    user_id_prefix=settings.backfill_matching_summaries_user_id_prefix,
                    team_name_prefix=settings.backfill_matching_summaries_team_name_prefix,
                )
            )
            logger.info(
                "Startup matching summary backfill finished exit_code=%s user_id_prefix=%s team_name_prefix=%s",
                exit_code,
                settings.backfill_matching_summaries_user_id_prefix,
                settings.backfill_matching_summaries_team_name_prefix,
            )
        except Exception:
            logger.exception("Startup matching summary backfill failed")
