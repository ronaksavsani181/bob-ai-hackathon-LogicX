FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# Copy application source
COPY . .

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
