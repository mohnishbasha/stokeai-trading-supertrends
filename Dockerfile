# syntax=docker/dockerfile:1
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
#
# Shape from ARCHITECTURE section 10.5. Sprint 0 omits alembic.ini and migrations/;
# S1-T01 adds them back. Every base image is pinned by digest (Dependabot keeps them fresh).

# ---- stage 1: UI dependencies and build ----
FROM --platform=$BUILDPLATFORM node:26-bookworm-slim@sha256:5df79989ed685e09f0a98019db4cebfb22fb9df1a53c0161664a011f7ff6b0f1 AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY ui/ ./
RUN npm run build

# ---- stage 2: Python dependencies (cached layer) ----
FROM python:3.15-slim-bookworm@sha256:96599df822d0e1c6bb700014a05c7f3c8cabc6e0f7ff3c4f9f69cee033b4b5d9 AS deps
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock VERSION ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

# ---- stage 3: build and install the project ----
FROM deps AS build
COPY README.md ./
COPY src/ ./src/
COPY config/ ./config/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

# ---- stage 4: minimal runtime ----
FROM python:3.15-slim-bookworm@sha256:96599df822d0e1c6bb700014a05c7f3c8cabc6e0f7ff3c4f9f69cee033b4b5d9 AS runtime
ARG VERSION=0.0.0
ARG COMMIT=unknown
ARG CREATED=unknown
LABEL org.opencontainers.image.title="Super Trends Market Agent" \
      org.opencontainers.image.description="Supertrend market agent: daily top buys and sells with justification" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT}" \
      org.opencontainers.image.created="${CREATED}" \
      org.opencontainers.image.source="https://github.com/mohnishbasha/stokeai-trading-supertrends" \
      org.opencontainers.image.vendor="Serverless Ventures LLC" \
      org.opencontainers.image.licenses="PolyForm-Noncommercial-1.0.0"
RUN groupadd -g 10001 supertrends && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin supertrends
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    SUPERTRENDS_VERSION=${VERSION} SUPERTRENDS_COMMIT=${COMMIT} SUPERTRENDS_UI_DIR=/app/ui
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/src /app/src
COPY --from=build /app/config /app/config
COPY --from=ui /ui/dist /app/ui
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["supertrends", "healthcheck", "--url", "http://127.0.0.1:8080"]
ENTRYPOINT ["supertrends"]
CMD ["serve", "--bind", "0.0.0.0:8080"]
