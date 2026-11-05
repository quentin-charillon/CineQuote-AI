from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.middleware.security import BrowserSecurityMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="API for the CineQuote AI movie trivia game.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_url).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.add_middleware(BrowserSecurityMiddleware, settings=settings)
    application.include_router(api_router)
    return application


app = create_app()

