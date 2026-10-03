FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
