#!/bin/sh
set -eu

MODE="${APP_MODE:-api}"

if [ "$MODE" = "dashboard" ]; then
  streamlit run ui/dashboard.py \
    --server.address 0.0.0.0 \
    --server.port "${PORT:-8501}"
else
  python api/server.py
fi

