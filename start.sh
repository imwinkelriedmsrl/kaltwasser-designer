#!/bin/bash
# Kaltwasser Designer — Startskript

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$APP_DIR/venv/bin/python"
LOG_FILE="$APP_DIR/kaltwasser-designer.log"

echo "Starte Kaltwasser Designer..."
echo "App-Verzeichnis: $APP_DIR"

cd "$APP_DIR"
exec "$PYTHON" -m streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    >> "$LOG_FILE" 2>&1
