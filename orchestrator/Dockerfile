ARG PYTHON_BASE=3.12-slim-bookworm

FROM python:${PYTHON_BASE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.20 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=common/uv.lock,target=common/uv.lock \
    --mount=type=bind,source=common/pyproject.toml,target=common/pyproject.toml \
    --mount=type=bind,source=orchestrator/uv.lock,target=orchestrator/uv.lock \
    --mount=type=bind,source=orchestrator/pyproject.toml,target=orchestrator/pyproject.toml \
    cd orchestrator && uv sync --frozen --no-install-project --no-editable

ADD common /app/common
ADD orchestrator /app/orchestrator

RUN --mount=type=cache,target=/root/.cache/uv \
    cd orchestrator && uv sync --frozen --no-editable


FROM python:${PYTHON_BASE} AS runtime

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y \
    git \
    curl \
    clang-tidy \ 
    cppcheck \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://get.docker.com | sh

# Copy uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.5.20 /uv /bin/uv

COPY --from=builder --chown=app:app /app/orchestrator/.venv /app/orchestrator/.venv

# Copy the static analyzer code
COPY orchestrator/src/buttercup/orchestrator/static_analyzer /app/orchestrator/.venv/lib/python3.12/site-packages/buttercup/orchestrator/static_analyzer

# Install static analyzer dependencies
RUN uv pip install --python /app/orchestrator/.venv/bin/python \
    aiohttp>=3.9.0

WORKDIR /app/orchestrator
ENV PATH=/app/orchestrator/.venv/bin:$PATH

