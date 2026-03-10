from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, board, chat, home, matching
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services import board_service


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
    app.include_router(home.router, prefix="/api/home", tags=["home"])
    app.include_router(matching.router, prefix="/api/matching", tags=["matching"])

    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        board_service.seed_board_data(db)
    finally:
        db.close()
