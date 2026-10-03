.PHONY: help setup start stop restart seed demo test benchmark clean lint

PYTHON ?= python
PIP ?= pip
DOCKER_COMPOSE ?= docker compose

help:
	@echo "FeatureHub & DataGuard Platform Commands:"
	@echo "  make setup      - Install Python dependencies locally and initialize project"
	@echo "  make start      - Launch all Docker services (Postgres, Redis, APIs, Dashboards, Observability)"
	@echo "  make stop       - Stop all Docker services"
	@echo "  make restart    - Restart Docker services"
	@echo "  make seed       - Generate synthetic domain data and populate database/parquet"
	@echo "  make demo       - Execute point-in-time correctness & ML prediction demo"
	@echo "  make test       - Run unit, integration, and E2E test suites"
	@echo "  make benchmark  - Execute reproducible latency & validation benchmark suites"
	@echo "  make lint       - Run ruff linter and type checks"
	@echo "  make clean      - Clean cache files and temporary artifacts"

setup:
	$(PIP) install -r requirements.txt
	$(PYTHON) scripts/setup.py

start:
	$(DOCKER_COMPOSE) up -d --build

stop:
	$(DOCKER_COMPOSE) down

restart: stop start

seed:
	$(PYTHON) scripts/seed_data.py
	$(PYTHON) scripts/generate_features.py

demo:
	$(PYTHON) scripts/demo_pit_and_inference.py

test:
	pytest tests/ -v --tb=short

benchmark:
	$(PYTHON) featurehub/benchmarks/run_benchmarks.py
	$(PYTHON) dataguard/benchmarks/run_benchmarks.py
	$(PYTHON) scripts/summarize_benchmarks.py

lint:
	ruff check .
	mypy featurehub/ dataguard/ --ignore-missing-imports

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
