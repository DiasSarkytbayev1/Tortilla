# syntax=docker/dockerfile:1.7

# ──────────────────────────────────────────────────────────────────────────────
# Stage 1: build a virtualenv with all dependencies using uv.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

# Install uv from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Copy lockfile + manifest first so dependency layer caches well.
COPY pyproject.toml uv.lock* ./

# Sync deps into a project-local venv at /app/.venv.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2: minimal runtime image.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

WORKDIR /app

# Pull the prebuilt venv and the source from the builder stage.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    POS_EXPORTS_DIR=/app/data/pos_exports

EXPOSE 8000

# Default command: start the FastAPI app. Override for ETL / analytics, e.g.
#   docker compose run --rm backend python -m app.cli generate 2026-05-04
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
