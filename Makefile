# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
#
# Shape and targets from ARCHITECTURE section 10.2. Targets that need a later sprint
# print "not available until Sprint N" and exit 0; each sprint restores its recipe verbatim.

SHELL := /bin/bash
GH_OWNER ?= mohnishbasha
VERSION  := $(shell tr -d '[:space:]' < VERSION)
COMMIT   := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
CREATED  := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
IMAGE    ?= ghcr.io/$(GH_OWNER)/stokeai-supertrends
CHART    := deploy/helm/stokeai-supertrends
CHART_REPO ?= oci://ghcr.io/$(GH_OWNER)/charts
KIND_CLUSTER ?= supertrends
NAMESPACE ?= supertrends
PROFILE  ?= kind
SMOKE_BASE_URL ?= http://localhost:8080
PLATFORMS ?= linux/amd64,linux/arm64
BUILD_ARGS := --build-arg VERSION=$(VERSION) --build-arg COMMIT=$(COMMIT) --build-arg CREATED=$(CREATED)

# Compose files reference ${IMAGE}:${VERSION}.
export IMAGE VERSION

.DEFAULT_GOAL := help
.PHONY: help setup build build-release check test coverage dev up down smoke demo demo-verify demo-down run-daily openapi \
        version-sync image image-multiarch image-push image-scan image-verify \
        helm-lint helm-package helm-push kind-up kind-load helm-install helm-test helm-uninstall kind-down

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: ## Check prerequisites and install dependencies
	@./scripts/check-prereqs.sh
	uv sync --locked
	npm --prefix ui ci

build: ## Build the UI and the Python wheel
	npm --prefix ui run build
	uv build --wheel

build-release: ## Reproducible release build (locked, clean)
	rm -rf dist ui/dist
	npm --prefix ui ci && npm --prefix ui run build
	uv sync --locked --no-dev && uv build --wheel

check: ## Lint, format check, type-check (Python and TypeScript)
	uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src
	npm --prefix ui run lint && npm --prefix ui run type-check
	./scripts/check-versions.sh

test: ## Unit tests
	uv run pytest tests/unit tests/golden -q
	npm --prefix ui run test -- --run

coverage: ## Coverage with thresholds
	uv run pytest tests/unit tests/golden tests/integration --cov=src/supertrends --cov-report=term --cov-report=xml
	npm --prefix ui run test -- --run --coverage
	uv run python scripts/check_coverage.py .coverage-thresholds.toml

dev: ## Native dev: Postgres in Compose, API and UI on the host with reload
	@echo "make dev: not available until Sprint 1"

up: ## Run the built image with Compose
	docker compose -f deploy/compose/docker-compose.local.yml up -d --wait

down: ## Stop Compose and remove volumes
	docker compose -f deploy/compose/docker-compose.local.yml down -v

smoke: ## Smoke suite against SMOKE_BASE_URL
	SMOKE_BASE_URL=$(SMOKE_BASE_URL) uv run pytest tests/smoke -q

demo: ## Local demo: full product on synthetic data, no keys needed
	@echo "make demo: not available until Sprint 3"

demo-verify: ## Check every product function against the running demo, write demo-report/
	@echo "make demo-verify: not available until Sprint 3"

demo-down: ## Stop the demo and remove its data
	@echo "make demo-down: not available until Sprint 3"

run-daily: ## Trigger the daily run locally
	@echo "make run-daily: not available until Sprint 3"

openapi: ## Regenerate docs/openapi.json and the UI client
	uv run supertrends config export-openapi --output docs/openapi.json
	@if [ -f ui/scripts/generate-api-client.sh ]; then ./ui/scripts/generate-api-client.sh; \
	else echo "make openapi: UI client generator not present, skipped"; fi

version-sync: ## Write VERSION into the checked files
	./scripts/version-sync.sh

image: ## Build the image for the local architecture
	docker buildx build $(BUILD_ARGS) -t $(IMAGE):$(VERSION) -t $(IMAGE):sha-$(COMMIT) --load .

image-multiarch: ## Build for linux/amd64 and linux/arm64 (no push)
	docker buildx build $(BUILD_ARGS) --platform $(PLATFORMS) -t $(IMAGE):$(VERSION) .

image-push: ## Build multi-arch, push, sign, attach SBOM and provenance
	@echo "make image-push: not available until Sprint 8"

image-scan: ## Vulnerability scan, fails on HIGH or CRITICAL
	@echo "make image-scan: not available until Sprint 8"

image-verify: ## Verify the image signature
	@echo "make image-verify: not available until Sprint 8"

helm-lint: ## Lint and template every profile
	@echo "make helm-lint: not available until Sprint 8"

helm-package: ## Package the chart at the current version
	@echo "make helm-package: not available until Sprint 8"

helm-push: ## Push the chart to the OCI registry
	@echo "make helm-push: not available until Sprint 8"

kind-up: ## Create the local kind cluster
	@echo "make kind-up: not available until Sprint 3"

kind-load: ## Load the local image into kind
	@echo "make kind-load: not available until Sprint 3"

helm-install: ## Install or upgrade the chart with PROFILE (default kind)
	@echo "make helm-install: not available until Sprint 3"

helm-test: ## Run Helm tests
	@echo "make helm-test: not available until Sprint 3"

helm-uninstall: ## Uninstall the release
	@echo "make helm-uninstall: not available until Sprint 8"

kind-down: ## Delete the kind cluster
	@echo "make kind-down: not available until Sprint 3"
