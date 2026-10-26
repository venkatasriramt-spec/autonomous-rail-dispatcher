# ==============================================================================
# Full-Stack Autonomous Railway Traffic Management Platform
# Multi-Stage Production Dockerfile for Google Cloud Run
# Stage 1: Build React 19 Frontend with Vite
# Stage 2: Production Python Runtime with Eclipse SUMO, PyTorch CPU & FastAPI
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build React Frontend
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Install dependencies with npm
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and compile production distribution
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Production Runtime (SUMO + PyTorch + FastAPI + Bundled Static UI)
# ------------------------------------------------------------------------------
FROM python:3.10-slim

# Prevent interactive prompts during apt installs and Python buffering
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SUMO_HOME=/usr/share/sumo \
    PATH="/usr/share/sumo/bin:${PATH}" \
    PYTHONPATH="/usr/share/sumo/tools:/app:${PYTHONPATH}" \
    PORT=8080 \
    HOST=0.0.0.0

# Install system dependencies: Eclipse SUMO, TraCI tools, and build tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    sumo \
    sumo-tools \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
COPY backend/requirements.txt /app/backend/requirements.txt

# Install PyTorch CPU-only first (avoids 2.5GB CUDA bloat), then project dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend, tracks, trains, dispatcher, and documentation files
COPY . /app

# Copy freshly compiled frontend distribution from Stage 1 into the container
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Cloud Run defaults to container port 8080
EXPOSE 8080

# Launch FastAPI via uvicorn (exec form allows container signal handling)
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
