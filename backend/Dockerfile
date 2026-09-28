# Stage 1: install dependencies
FROM python:3.12-slim AS deps

WORKDIR /build

# Install system dependencies required for psycopg2-binary and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: application image
FROM python:3.12-slim AS app

WORKDIR /app

# Copy installed packages from deps stage
COPY --from=deps /install /usr/local

# Create non-root user
RUN useradd -r -u 1001 appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

# Copy application source
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
