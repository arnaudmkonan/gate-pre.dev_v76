# =============================================================================
# Documentation Ingestion Platform - Makefile
# =============================================================================

.PHONY: help up down build logs restart clean status shell-api shell-db

# Default target
help:
	@echo "Documentation Ingestion Platform - Docker Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  up          Start all services in the background"
	@echo "  up-build    Build and start all services"
	@echo "  down        Stop all services"
	@echo "  build       Build all Docker images"
	@echo "  logs        View logs from all services"
	@echo "  logs-api    View API logs only"
	@echo "  logs-worker View Worker logs only"
	@echo "  restart     Restart all services"
	@echo "  status      Show status of all services"
	@echo "  clean       Remove all containers, volumes, and images"
	@echo "  shell-api   Open shell in API container"
	@echo "  shell-db    Open psql in PostgreSQL container"
	@echo "  migrate     Run database migrations"
	@echo "  test        Run API tests"

# Start all services
up:
	docker compose up -d
	@echo ""
	@echo "✅ Services started!"
	@echo ""
	@echo "📍 Access points:"
	@echo "   Frontend:  http://localhost:3000"
	@echo "   API:       http://localhost:8000"
	@echo "   API Docs:  http://localhost:8000/docs"
	@echo "   PGWeb:     http://localhost:8081"
	@echo "   Flower:    http://localhost:5555 (admin:admin)"
	@echo ""

# Build and start
up-build:
	docker compose up -d --build
	@echo ""
	@echo "✅ Services built and started!"

# Stop all services
down:
	docker compose down

# Build images
build:
	docker compose build

# View all logs
logs:
	docker compose logs -f

# View API logs
logs-api:
	docker compose logs -f api

# View Worker logs
logs-worker:
	docker compose logs -f worker

# Restart all services
restart:
	docker compose restart

# Show status
status:
	docker compose ps

# Clean everything
clean:
	docker compose down -v --rmi local
	@echo "✅ Cleaned up all containers, volumes, and local images"

# Shell into API container
shell-api:
	docker compose exec api bash

# Shell into PostgreSQL
shell-db:
	docker compose exec postgres psql -U postgres -d doc_ingestion

# Run migrations
migrate:
	docker compose exec api alembic upgrade head

# Run tests
test:
	docker compose exec api pytest tests/ -v
