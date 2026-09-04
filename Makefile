.PHONY: setup run eval ingest clean docker-build docker-run help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Generate data, ingest into DuckDB + ChromaDB
	py src/generate_data.py
	py src/db_setup.py
	py src/ingest.py

run: ## Launch Streamlit app
	py -m streamlit run src/app.py

eval: ## Run evaluation suite
	py eval/run_eval.py

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
