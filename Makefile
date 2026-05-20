# pricestream — convenience targets.

.PHONY: help up down build logs ps shell migrate test test-cov lint fmt token bootstrap clean

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack via docker compose.
	docker compose up --build

down: ## Stop and remove containers.
	docker compose down -v

build: ## Build images without starting.
	docker compose build

logs: ## Tail logs from every service.
	docker compose logs -f --tail=50

ps: ## Show running services.
	docker compose ps

shell: ## Open a Django shell inside the web container.
	docker compose exec web python manage.py shell

migrate: ## Apply migrations.
	docker compose exec web python manage.py migrate

bootstrap: ## Seed default instruments.
	docker compose exec web python manage.py bootstrap_instruments

token: ## Create a superuser + DRF token (USERNAME=alice make token).
	docker compose exec web python manage.py createsuperuser
	@echo "Now run: docker compose exec web python manage.py drf_create_token <username>"

test: ## Run pytest inside the web container.
	docker compose run --rm web pytest -v

test-cov: ## Run pytest with coverage.
	docker compose run --rm web pytest --cov=apps --cov-report=term-missing

lint: ## Run ruff.
	docker compose run --rm web ruff check .

fmt: ## Auto-fix ruff issues.
	docker compose run --rm web ruff check --fix .

clean: ## Remove caches.
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
