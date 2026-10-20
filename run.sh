#!/usr/bin/env bash
cd "$(dirname "$0")/backend" || exit 1
python3 -m pip install -r requirements.txt
echo "Starting FinBridge at http://localhost:8000 (Ctrl+C to stop)"
python3 -m uvicorn app.main:app --port 8000
