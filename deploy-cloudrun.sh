#!/usr/bin/env bash
#
# deploy-cloudrun.sh — Deploy borsa-mcp to Google Cloud Run (EU / KVKK).
#
# Idempotent: safe to re-run. `gcloud run deploy` creates the service on first
# run and rolls out a new revision on subsequent runs. Re-running the secret
# bootstrap block (below) is also safe — it tolerates "already exists".
#
# ---------------------------------------------------------------------------
# CONFIG SOURCE (matches the real observability-derived load profile):
#   ~3.8M tool calls/month, bursty, almost entirely I/O-bound
#   (external APIs: Yahoo Finance, KAP, TEFAS, BtcTurk, Coinbase, doviz.com, TCMB EVDS)
#   duration: p50 437ms, avg 4.4s, p95 25s, p99 96s
#   memory: peak 399MB, avg 378MB  -> 512Mi is enough (1Gi was over-provisioned)
# ---------------------------------------------------------------------------

set -euo pipefail

# --- Tunables (override via env, e.g. PROJECT_ID=foo ./deploy-cloudrun.sh) ---
SERVICE="${SERVICE:-borsa-mcp}"
REGION="${REGION:-europe-west1}"          # Tier-1 EU region, KVKK-compliant
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: PROJECT_ID is empty. Run 'gcloud config set project <id>' or pass PROJECT_ID=..." >&2
  exit 1
fi

echo ">>> Deploying '${SERVICE}' to project '${PROJECT_ID}' in region '${REGION}'"

# ---------------------------------------------------------------------------
# ONE-TIME BOOTSTRAP (run these manually once per project; left as comments).
# These are NOT executed automatically so we never touch secrets unattended.
#
#   # Enable required APIs:
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
#       secretmanager.googleapis.com artifactregistry.googleapis.com \
#       --project "${PROJECT_ID}"
#
#   # Create the EVDS_API_KEY secret (paste the real key at the prompt; never commit it):
#   printf '%s' 'YOUR_REAL_EVDS_KEY' | gcloud secrets create EVDS_API_KEY \
#       --data-file=- --replication-policy=automatic --project "${PROJECT_ID}"
#   # To rotate later:
#   #   printf '%s' 'NEW_KEY' | gcloud secrets versions add EVDS_API_KEY --data-file=- --project "${PROJECT_ID}"
#
#   # Grant the Cloud Run runtime service account read access to the secret:
#   PROJNUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
#   gcloud secrets add-iam-policy-binding EVDS_API_KEY \
#       --member="serviceAccount:${PROJNUM}-compute@developer.gserviceaccount.com" \
#       --role="roles/secretmanager.secretAccessor" --project "${PROJECT_ID}"
#
#   # (Optional) DATABASE_URL — only if you move off the SQLite fallback:
#   #   printf '%s' 'postgresql://...' | gcloud secrets create DATABASE_URL --data-file=- --project "${PROJECT_ID}"
# ---------------------------------------------------------------------------

# Build --set-secrets only for secrets that actually exist, so the deploy
# doesn't fail when an optional secret (DATABASE_URL) hasn't been created.
SECRET_FLAGS=()
secret_exists() { gcloud secrets describe "$1" --project "${PROJECT_ID}" >/dev/null 2>&1; }

if secret_exists EVDS_API_KEY; then
  SECRET_FLAGS+=("--set-secrets=EVDS_API_KEY=EVDS_API_KEY:latest")
else
  echo "WARNING: secret EVDS_API_KEY not found — deploying without it (EVDS data-fetch actions will be disabled; catalog/search still work)." >&2
fi

if secret_exists DATABASE_URL; then
  SECRET_FLAGS+=("--set-secrets=DATABASE_URL=DATABASE_URL:latest")
fi

# ---------------------------------------------------------------------------
# DEPLOY. Parameters are derived from the load profile above:
#   --memory 512Mi          peak is 399MB; 1Gi was over-provisioned
#   --cpu 1                 active CPU use is low (I/O-bound)
#   --concurrency 80        I/O-bound work shares one instance -> fewer instances -> lower bill
#   --min-instances 0       traffic is near-continuous so instances stay warm; raise to 1 if cold starts bite
#   --max-instances 10      denial-of-wallet ceiling
#   --timeout 120           covers the p99=96s tail
#   --no-cpu-throttling absent => request-based billing (CPU only allocated during requests):
#                          this is the cost win for I/O-bound workloads. Do NOT add --no-cpu-throttling.
#   --allow-unauthenticated public MCP endpoint
# ---------------------------------------------------------------------------
gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 120 \
  --allow-unauthenticated \
  --set-env-vars "CONTAINER_ENV=1,PYTHONUNBUFFERED=1" \
  "${SECRET_FLAGS[@]}"

# ---------------------------------------------------------------------------
# Post-deploy: print URL and verify /health.
# ---------------------------------------------------------------------------
URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT_ID}" \
  --region "${REGION}" --format='value(status.url)')"

echo ">>> Service URL: ${URL}"
echo ">>> MCP endpoint: ${URL}/mcp/"
echo ">>> Verifying /health ..."
if curl -fsS "${URL}/health" ; then
  echo ""
  echo ">>> Health OK."
else
  echo "" >&2
  echo "WARNING: /health did not return success. Check logs:" >&2
  echo "  gcloud run services logs read ${SERVICE} --region ${REGION} --project ${PROJECT_ID}" >&2
  exit 1
fi
