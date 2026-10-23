# `py` is the Windows launcher only - it does not exist on macOS/Linux or in
# the python:3.12-slim image. Override with `make PY=python3`.
PY ?= python

.PHONY: setup dld run run-api run-ui eval eval-fresh ingest reports setup-db clean docker-build docker-run help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Build everything from the DLD exports in data/raw/dld/ (see docs/plans)
	$(PY) src/dld_loader.py
	$(PY) src/db_setup.py
	$(PY) src/build_reports.py
	$(PY) src/ingest.py

dld: setup ## Alias: rebuild from new DLD exports

run-api: ## Launch FastAPI backend on :8000
	$(PY) -m uvicorn api.main:app --reload --port 8000

run-ui: ## Launch Next.js frontend on :3000
	cd frontend && npm run dev

run: ## Launch Streamlit app (legacy UI)
	$(PY) -m streamlit run src/app.py

eval: ## Run evaluation suite (resumes prior successes; loads .env)
	$(PY) eval/run_eval.py

eval-fresh: ## Re-run all eval questions (ignore prior results)
	$(PY) eval/run_eval.py --fresh

ingest: ## Re-ingest data into ChromaDB only
	$(PY) src/ingest.py

reports: ## Regenerate per-community market reports from DuckDB, then re-ingest
	$(PY) src/build_reports.py
	$(PY) src/ingest.py

setup-db: ## Rebuild DuckDB only (from data/processed/dld_*.parquet)
	$(PY) src/db_setup.py

clean: ## Remove generated data and DB
	rm -rf data/dubai_properties.duckdb chroma_db/* data/processed/*

docker-build: ## Build Docker image
	docker compose build

docker-run: ## Run in Docker
	docker compose up

docker-stop: ## Stop Docker containers
	docker compose down
