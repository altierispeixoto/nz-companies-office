# syntax=docker/dockerfile:1.4

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/opt/uv-cache/

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN useradd -m -s /bin/bash app-user

WORKDIR /app
RUN chown app-user:app-user /app

USER app-user

COPY --chown=app-user:app-user pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/opt/uv-cache,uid=$(id -u app-user) \
    uv sync --no-install-project --frozen

COPY --chown=app-user:app-user . .

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN useradd -m -s /bin/bash app-user

WORKDIR /app
RUN chown app-user:app-user /app

COPY --from=builder --chown=app-user:app-user /app /app

USER app-user

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["uv", "run"]
CMD ["nz-companies-office"]
