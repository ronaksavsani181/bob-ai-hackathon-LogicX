FROM python:3.11-slim

WORKDIR /app

# Build tools are retained for scientific Python packages when a binary wheel is unavailable.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the packages before the editable install so Python can import them at runtime.
COPY . .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
