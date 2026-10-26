#!/usr/bin/env bash
# ==============================================================================
# Deploy Full-Stack Autonomous Railway Traffic Management Platform to Cloud Run
# Bundles React 19 Frontend + Python 3.10 Backend (SUMO, PyTorch, WebSockets)
# ==============================================================================
set -euo pipefail

SERVICE_NAME="${1:-railway-platform}"
REGION="${2:-us-central1}"
PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo '')"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: No active GCP project configured. Run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

echo "=========================================================="
echo " Deploying Full-Stack Railway Platform to Google Cloud Run "
echo "=========================================================="
echo " Project:       $PROJECT_ID"
echo " Service Name:  $SERVICE_NAME"
echo " Region:        $REGION"
echo " Source:        $(pwd)"
echo " Resources:     4 vCPUs / 8 GiB RAM (Gen2, Always Allocated)"
echo "=========================================================="

# 1. Enable required Google Cloud APIs
echo "--> Enabling required APIs (Cloud Run, Cloud Build, Artifact Registry)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project="$PROJECT_ID"

# 2. Delete previous standalone backend service if it exists
if [ "$SERVICE_NAME" != "railway-backend" ]; then
    echo "--> Deleting previous standalone backend service [railway-backend]..."
    gcloud run services delete railway-backend --region "$REGION" --project "$PROJECT_ID" --quiet 2>/dev/null || true
fi

# 3. Build container with Cloud Build and Deploy to Cloud Run (Ultra-High-Performance Tier)
echo "--> Building full-stack container and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --quiet \
  --cpu 4 \
  --memory 8Gi \
  --execution-environment gen2 \
  --no-cpu-throttling \
  --min-instances 1 \
  --max-instances 1 \
  --concurrency 80 \
  --timeout 3600 \
  --session-affinity \
  --set-env-vars SIM_MODE=LIVE_SUMO,CORS_ORIGINS="*"

# 4. Retrieve live service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')

echo ""
echo "=========================================================="
echo " Full-Stack Platform Deployed Successfully!"
echo "=========================================================="
echo " Web Application URL:   $SERVICE_URL/"
echo " Simulation Dashboard:  $SERVICE_URL/simulation"
echo " Timetable Query:       $SERVICE_URL/query"
echo " Model Benchmarks:      $SERVICE_URL/about"
echo " Swagger API Docs:      $SERVICE_URL/docs"
echo " Liveness Health Check: $SERVICE_URL/health"
echo " WebSocket Telemetry:   wss://${SERVICE_URL#https://}/ws/telemetry"
echo "=========================================================="
