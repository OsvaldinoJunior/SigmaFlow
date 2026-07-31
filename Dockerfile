# Dockerfile for SigmaFlow Enterprise
# Multi-stage build for production

# ============================================================================
# Stage 1: Frontend Builder (Next.js)
# ============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN npm run build

# ============================================================================
# Stage 2: Python Dependencies Builder
# ============================================================================
FROM python:3.11-slim AS python-builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python project files
COPY pyproject.toml uv.lock ./

# Install uv and Python dependencies
RUN pip install --no-cache-dir uv && \
    uv pip install --system -e .

# ============================================================================
# Stage 3: Production Image
# ============================================================================
FROM python:3.11-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r sigmaflow && useradd -r -g sigmaflow sigmaflow

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=sigmaflow:sigmaflow . .

# Copy built frontend from frontend-builder
COPY --from=frontend-builder --chown=sigmaflow:sigmaflow /app/frontend/.next/standalone ./frontend/
COPY --from=frontend-builder --chown=sigmaflow:sigmaflow /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder --chown=sigmaflow:sigmaflow /app/frontend/public ./frontend/public

# Create storage directory
RUN mkdir -p /app/storage && chown -R sigmaflow:sigmaflow /app/storage

# Switch to non-root user
USER sigmaflow

# Expose ports
EXPOSE 8000 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - run both API and frontend
# Using a process manager like supervisord or just run API (frontend can be served separately)
CMD ["uvicorn", "sigmaflow.api.main:app", "--host", "0.0.0.0", "--port", "8000"]