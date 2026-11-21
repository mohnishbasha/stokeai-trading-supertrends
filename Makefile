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
RELEASE  ?= supertrends
NAMESPACE ?= supertrends
PROFILE  ?= kind
# Host port that reaches the API: Compose publishes it, and kind maps NodePort 30080 to it
# (deploy/kind/cluster.yaml). 8080 is the Compose default; the kind default is 18080.
KIND_HOST_PORT := $(or $(SUPERTRENDS_HOST_PORT),18080)
# Optional: override the pinned node image (for a local kind older than the pinned image needs).
KIND_NODE_IMAGE ?=
# helm and kubectl must never act on a cluster other than the one kind-up created.
KUBE_CONTEXT ?= $(if $(filter kind,$(PROFILE)),kind-$(KIND_CLUSTER))
HELM_CTX := $(if $(KUBE_CONTEXT),--kube-context $(KUBE_CONTEXT))
SMOKE_BASE_URL ?= http://localhost:$(or $(SUPERTRENDS_HOST_PORT),8080)
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

# Local daily run (FR-905). With SUPERTRENDS_DATABASE_URL set it runs in this environment
# ("make dev"); otherwise in the Compose app image against the Compose Postgres ("make up").
# DATE=YYYY-MM-DD picks the trade date; without it, a holiday prints "market closed" and exits 0.
run-daily: ## Run the daily pipeline locally (DATE=YYYY-MM-DD optional)
ifdef SUPERTRENDS_DATABASE_URL
	uv run supertrends run daily $(if $(DATE),--date $(DATE))
else
	docker compose -f deploy/compose/docker-compose.local.yml run --rm app run daily $(if $(DATE),--date $(DATE))
endif

openapi: ## Regenerate docs/openapi.json and the UI client
	@echo "make openapi: not available until Sprint 3"

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

helm-lint: ## Lint and template every profile (values.yaml and each values-<profile>.yaml)
	helm lint $(CHART)
	helm template $(RELEASE) $(CHART) > /dev/null
	@for f in $(CHART)/values-*.yaml; do \
	  echo "== $$f"; \
	  helm lint $(CHART) -f $$f || exit 1; \
	  helm template $(RELEASE) $(CHART) -f $$f > /dev/null || exit 1; \
	done

helm-package: ## Package the chart at the current version
	@echo "make helm-package: not available until Sprint 8"

helm-push: ## Push the chart to the OCI registry
	@echo "make helm-push: not available until Sprint 8"

kind-up: ## Create the local kind cluster (host port from SUPERTRENDS_HOST_PORT, default 18080)
	sed -e "s/hostPort: 18080/hostPort: $(KIND_HOST_PORT)/" \
	  $(if $(KIND_NODE_IMAGE),-e "s#image: kindest/node:.*#image: $(KIND_NODE_IMAGE)#") deploy/kind/cluster.yaml \
	  | kind create cluster --name $(KIND_CLUSTER) --config -

kind-load: ## Load the local image into kind
	kind load docker-image $(IMAGE):$(VERSION) --name $(KIND_CLUSTER)

helm-install: ## Install or upgrade the chart with PROFILE (default kind)
	helm upgrade --install $(RELEASE) $(CHART) -n $(NAMESPACE) --create-namespace $(HELM_CTX) \
	  -f $(CHART)/values-$(PROFILE).yaml \
	  --set image.repository=$(IMAGE) --set image.tag=$(VERSION) \
	  --wait --timeout 5m

helm-test: ## Run Helm tests
	helm test $(RELEASE) -n $(NAMESPACE) $(HELM_CTX) --logs

helm-uninstall: ## Uninstall the release
	@echo "make helm-uninstall: not available until Sprint 8"

kind-down: ## Delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)
