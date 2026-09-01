import logging

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
from app.routers import health, jobs, profile, resume, setup

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Job Assistant", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(setup.router)
    application.include_router(resume.router)
    application.include_router(profile.router)
    application.include_router(jobs.router)
    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(RequestValidationError, request_validation_error_handler)
    application.add_middleware(DbCommitMiddleware)
    return application


app = create_app()
