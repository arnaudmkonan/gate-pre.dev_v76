# =============================================================================
# GATE Platform — Makefile
# =============================================================================
#
# Development and production build commands.
#
# Usage:
#   make help          — show all targets
#   make up            — start dev environment
#   make build-api     — build production API image
#   make build-web     — build production web image
#   make build-all     — build both production images
#   make provision     — provision a new customer instance
#

VERSION ?= $(shell git describe --tags --always 2>/dev/null || echo "dev")
REGISTRY ?= gate-platform
API_IMAGE = $(REGISTRY)/api
WEB_IMAGE = $(REGISTRY)/web

.PHONY: help up up-build down build logs logs-api logs-worker restart status \
        clean shell-api shell-db migrate test \
        build-api build-web build-all push provision lint

# ─────────────────── Help ───────────────────
help:
	@echo ""
	@echo "  GATE Platform — Build & Deploy Commands"
	@echo "  ════════════════════════════════════════"
	@echo ""
	@echo "  Development:"
	@echo "    make up           Start all services (detached)"
	@echo "    make up-build     Build and start all services"
	@echo "    make down         Stop all services"
	@echo "    make logs         View all service logs"
	@echo "    make logs-api     View API logs only"
	@echo "    make logs-worker  View Worker logs only"
	@echo "    make restart      Restart all services"
	@echo "    make status       Show status of all services"
	@echo "    make shell-api    Open shell in API container"
	@echo "    make shell-db     Open psql in DB container"
	@echo "    make migrate      Run database migrations"
	@echo "    make test         Run API tests"
	@echo "    make lint         Run linting checks"
	@echo ""
	@echo "  Production Images:"
	@echo "    make build-api    Build API image ($(API_IMAGE):$(VERSION))"
	@echo "    make build-web    Build web image ($(WEB_IMAGE):$(VERSION))"
	@echo "    make build-all    Build both images"
	@echo "    make push         Push images to registry"
	@echo ""
	@echo "  Instance Management:"
	@echo "    make provision ID=acme NAME=\"Acme LLC\" EMAIL=admin@acme.com SUB=acme"
	@echo ""
	@echo "  Current version: $(VERSION)"
	@echo ""

# ─────────────────── Development ───────────────────

up:
	docker compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "📍 Access points:"
	@echo "   Frontend:  http://localhost:3000"
	@echo "   API:       http://localhost:8000"
	@echo "   API Docs:  http://localhost:8000/docs"
	@echo "   Flower:    http://localhost:5555"
	@echo ""

up-build:
	docker compose up -d --build
	@echo ""
	@echo "✅ Services built and started!"

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

restart:
	docker compose restart

status:
	docker compose ps

clean:
	docker compose down -v --rmi local
	@echo "✅ Cleaned up all containers, volumes, and local images"

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U postgres -d doc_ingestion

migrate:
	docker compose exec api alembic upgrade head

test:
	docker compose exec api pytest tests/ -v

lint:
	@echo "=== Python linting ==="
	cd services/api && python -m py_compile app/main.py && echo "✅ main.py OK"
	cd services/api && python -c "from app.main import app; print('✅ App imports OK')"
	@echo ""
	@echo "=== TypeScript check ==="
	cd apps/web && npx tsc --noEmit && echo "✅ TypeScript OK"

# ─────────────────── Production Images ───────────────────

build-api:
	@echo "Building $(API_IMAGE):$(VERSION)..."
	docker build \
		-t $(API_IMAGE):$(VERSION) \
		-t $(API_IMAGE):latest \
		--build-arg BUILD_VERSION=$(VERSION) \
		-f services/api/Dockerfile \
		services/api
	@echo "✅ $(API_IMAGE):$(VERSION) built"

build-web:
	@echo "Building $(WEB_IMAGE):$(VERSION)..."
	docker build \
		-t $(WEB_IMAGE):$(VERSION) \
		-t $(WEB_IMAGE):latest \
		--build-arg BUILD_VERSION=$(VERSION) \
		-f apps/web/Dockerfile \
		apps/web
	@echo "✅ $(WEB_IMAGE):$(VERSION) built"

build-all: build-api build-web
	@echo ""
	@echo "✅ All production images built:"
	@docker images | grep gate-platform | head -6

push:
	@echo "Pushing images..."
	docker push $(API_IMAGE):$(VERSION)
	docker push $(API_IMAGE):latest
	docker push $(WEB_IMAGE):$(VERSION)
	docker push $(WEB_IMAGE):latest
	@echo "✅ Images pushed"

# ─────────────────── Instance Management ───────────────────

provision:
ifndef ID
	$(error ID is required. Usage: make provision ID=acme NAME="Acme LLC" EMAIL=admin@acme.com SUB=acme)
endif
ifndef NAME
	$(error NAME is required)
endif
ifndef EMAIL
	$(error EMAIL is required)
endif
ifndef SUB
	$(error SUB is required)
endif
	./provisioning/scripts/provision.sh "$(ID)" "$(NAME)" "$(EMAIL)" "$(SUB)" "$(VERSION)"
	@echo ""
	@echo "✅ Instance provisioned with platform version $(VERSION)"
