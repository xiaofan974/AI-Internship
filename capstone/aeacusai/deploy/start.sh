#!/usr/bin/env bash
# Render start command for aeacusai-demo. Bind to 0.0.0.0 and $PORT.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python deploy/materialize_week4_bundle.py

PORT="${PORT:-8501}"
exec streamlit run streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port "$PORT" \
  --server.headless true \
  --server.fileWatcherType none \
  --browser.gatherUsageStats false
