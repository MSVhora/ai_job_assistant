import logging
from typing import TYPE_CHECKING, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import DbCommitMiddleware
from app.core.errors import (
    DomainError,
    domain_error_handler,
    request_validation_error_handler,
)
from app.core.pagination import TOTAL_COUNT_HEADER
from app.routers import ats, health, jobs, matches, profile, resume, setup

if TYPE_CHECKING:
    from starlette.types import ExceptionHandler

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Job Assistant", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
        expose_headers=[TOTAL_COUNT_HEADER],
    )
    application.include_router(health.router)
    application.include_router(setup.router)
    application.include_router(resume.router)
    application.include_router(profile.router)
    application.include_router(ats.router)
    application.include_router(jobs.router)
    application.include_router(matches.router)
    application.add_exception_handler(DomainError, cast("ExceptionHandler", domain_error_handler))
    application.add_exception_handler(
        RequestValidationError, cast("ExceptionHandler", request_validation_error_handler)
    )
    application.add_middleware(DbCommitMiddleware)
    return application


app = create_app()
