#!/bin/sh
# Build the derived artefacts the API needs, then start it.
#
# The previous image copied chroma_db/ from the build context, but that path is
# in .dockerignore and .gitignore - so the build failed on a clean clone. Even
# with the copy fixed, nothing ever created data/dubai_properties.duckdb, and
# rag.py opens it read-only at import time, so the container died on startup.
set -e

# Always rebuild. db_setup is idempotent (CREATE IF NOT EXISTS, then DELETE and
# reload each table) and it is how a schema addition such as price_history
# reaches an existing ./data volume. Guarding on "DB file exists" left upgraded
# containers without the new table, so /trends silently served nothing.
echo "[entrypoint] Building DuckDB from data/raw CSVs"
python src/db_setup.py

if [ ! -d chroma_db ] || [ -z "$(ls -A chroma_db 2>/dev/null)" ]; then
    echo "[entrypoint] No ChromaDB store, ingesting market reports"
    python src/ingest.py
fi

exec uvicorn api.main:app --host 0.0.0.0 --port 8000
