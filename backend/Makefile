.PHONY: help test test-py test-go build-go docker-up docker-down docker-logs docker-build clean

help: ## Show this help message
	@echo "Available commands in NurCRM Backend:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

test: test-py test-go ## Run all automated tests (Python & Go)

test-py: ## Run Python domain and use-case unit tests
	PYTHONPATH=backend:. backend/.venv/bin/pytest -v backend/tests/test_domain_and_use_cases.py

test-go: ## Run Go availability engine unit tests
	cd services/public-gateway && go test -v ./...

build-go: ## Compile all Go microservices into bin/ directories
	@echo "Building public-gateway..."
	cd services/public-gateway && go build -o bin/public-gateway ./cmd/main.go
	@echo "Building scheduler-worker..."
	cd services/scheduler-worker && go build -o bin/scheduler-worker ./cmd/main.go
	@echo "Building realtime-gateway..."
	cd services/realtime-gateway && go build -o bin/realtime-gateway ./cmd/main.go
	@echo "All Go microservices compiled successfully into bin/."

docker-up: ## Start all microservices and infrastructure via Docker Compose
	docker compose -f deploy/docker-compose.yml up -d

docker-down: ## Stop all Docker Compose containers
	docker compose -f deploy/docker-compose.yml down

docker-build: ## Build Docker Compose images
	docker compose -f deploy/docker-compose.yml build

docker-logs: ## View live logs from Docker Compose
	docker compose -f deploy/docker-compose.yml logs -f

clean: ## Clean up bytecode and cache files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
