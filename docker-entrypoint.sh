#!/bin/sh
# Build the derived artefacts the API needs, then start it.
#
# Everything is rebuilt from the DLD exports in data/raw/dld/ on each start:
# the loader cleans them, db_setup builds DuckDB and its views, build_reports
# writes one report per community and ingest embeds them. The exports are a
# manual download (the DLD gateway needs a captcha), so they must be in place.
set -e

if ! ls data/raw/dld/transactions-*.csv >/dev/null 2>&1; then
    echo "[entrypoint] No DLD exports in data/raw/dld/ - see docs/plans/2026-10-23-real-dld-data.md" >&2
    exit 1
fi

echo "[entrypoint] Building from DLD exports"
python src/dld_loader.py
python src/db_setup.py
python src/build_reports.py
python src/ingest.py

exec uvicorn api.main:app --host 0.0.0.0 --port 8000
