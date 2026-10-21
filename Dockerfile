FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source. data/raw is the input for the entrypoint's build step;
# data/dubai_properties.duckdb and chroma_db/ are gitignored build artifacts, so
# they are generated at container start rather than baked in (COPY of a
# dockerignored path fails the build on a clean clone).
COPY api/ ./api/
COPY src/ ./src/
COPY data/raw/ ./data/raw/
COPY eval/ ./eval/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
