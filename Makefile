.PHONY: setup run run-api run-ui eval ingest clean docker-build docker-run help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Generate data, ingest into DuckDB + ChromaDB
	py src/generate_data.py
	py src/db_setup.py
	py src/ingest.py

run-api: ## Launch FastAPI backend on :8000
	py -m uvicorn api.main:app --reload --port 8000

run-ui: ## Launch Next.js frontend on :3000
	cd frontend && npm run dev

run: ## Launch Streamlit app (legacy UI)
	py -m streamlit run src/app.py

eval: ## Run evaluation suite (resumes prior successes; loads .env)
	py eval/run_eval.py

eval-fresh: ## Re-run all eval questions (ignore prior results)
	py eval/run_eval.py --fresh

ingest: ## Re-ingest data into ChromaDB only
	py src/ingest.py

setup-db: ## Rebuild DuckDB only
	py src/generate_data.py
	py src/db_setup.py

clean: ## Remove generated data and DB
	rm -rf data/dubai_properties.duckdb chroma_db/* data/processed/*

docker-build: ## Build Docker image
	docker compose build

docker-run: ## Run in Docker
	docker compose up

docker-stop: ## Stop Docker containers
	docker compose down
