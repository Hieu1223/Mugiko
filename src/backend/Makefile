# ==============================================================================
# Configuration & Environment
# ==============================================================================

# Export project root so Python scripts can resolve absolute paths
export PROJECT_ROOT := $(CURDIR)

# Directory containing Python scripts
SCRIPTS_DIR := $(PROJECT_ROOT)/scripts

# Python executable inside the virtual environment (adjust path if venv is elsewhere)
PYTHON := $(PROJECT_ROOT)/.venv/Scripts/python.exe

# Load .env.local if it exists and export variables to the environment
-include .env.local
export

# Go build caches
GOCACHE ?= $(PROJECT_ROOT)/.cache/go-build
GOMODCACHE ?= $(PROJECT_ROOT)/.cache/go-mod
export GOCACHE
export GOMODCACHE

# Docker DB used by `make migrate-docker` (override as needed)
DOCKER_NETWORK ?= scripts_default
DOCKER_DB_HOST ?= postgres
DOCKER_DB_PORT ?= 5432
DOCKER_DB_NAME ?= mugiko
DOCKER_DB_USER ?= postgres
DOCKER_DB_PASSWORD ?= postgres




# ==============================================================================
# Phony Targets
# ==============================================================================
.PHONY: build run run-dev setup setup-dev clean help migrate migrate-docker

# ==============================================================================
# Help
# ==============================================================================
help:
	@echo "Available commands:"
	@echo "  make build      - Build the Go server"
	@echo "  make run        - Build and run the server"
	@echo "  make run-dev    - Run server with auto DB rollback"
	@echo "  make setup      - Initialize DB (schema + seed)"
	@echo "  make migrate    - Apply pending SQL migrations"
	@echo "  make migrate-docker - Apply pending migrations to the Docker DB"
	@echo "  make clean      - Remove build artifacts and caches"

# ==============================================================================
# Go Server Targets
# ==============================================================================

build:
	go build -o build/main ./cmd/server

run: build
	xcopy /E /I .\asset ".\build\asset"
	./build/main

run-dev: build
	$(PYTHON) $(SCRIPTS_DIR)/run-dev.py

# ==============================================================================
# Database Targets
# ==============================================================================

setup:
	@echo "Running database setup..."
	$(PYTHON) $(SCRIPTS_DIR)/common/run_sql.py -f $(SCRIPTS_DIR)/sql/setup/schema.sql
	$(PYTHON) $(SCRIPTS_DIR)/common/run_sql.py -f $(SCRIPTS_DIR)/sql/setup/seed.sql

migrate:
	@echo "Applying pending database migrations..."
	$(PYTHON) $(SCRIPTS_DIR)/migrate.py

migrate-docker:
	@echo "Applying pending database migrations in Docker..."
	docker run --rm \
		--network $(DOCKER_NETWORK) \
		-e PGHOST=$(DOCKER_DB_HOST) \
		-e PGPORT=$(DOCKER_DB_PORT) \
		-e PGUSER=$(DOCKER_DB_USER) \
		-e PGPASSWORD=$(DOCKER_DB_PASSWORD) \
		-e PGDATABASE=$(DOCKER_DB_NAME) \
		-v "$(SCRIPTS_DIR)/sql/migrations:/migrations:ro" \
		-v "$(SCRIPTS_DIR)/migrate-docker.sh:/migrate-docker.sh:ro" \
		postgres:15-alpine \
		sh /migrate-docker.sh

# ==============================================================================
# Cleanup
# ==============================================================================

clean:
	if exist build rmdir /s /q build
	if exist .cache rmdir /s /q .cache
	if exist backup rmdir /s /q backup


reset-db:
	$(PYTHON) $(SCRIPTS_DIR)/reset-db.py