# Production Dockerfile for JOB-HUNTER API & Playwright Worker on Render
FROM python:3.11-slim

# Prevent interactive prompts and set Python behavior
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000

WORKDIR /app

# Install system dependencies for Playwright and Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .

# Install Python packages (including PostgreSQL drivers: psycopg2 and psycopg v3)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary "psycopg[binary]" uvicorn fastapi supabase python-multipart python-docx

# Install Playwright browser binaries
RUN playwright install chromium

# Create runtime storage directories
RUN mkdir -p /app/cv/variants /app/logs/screenshots

# Copy application source code
COPY app/ ./app/
COPY data/ ./data/
COPY run.py .

# Expose server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8000/api/stats/dashboard || exit 1

# Start the FastAPI application server
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
