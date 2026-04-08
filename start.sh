#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

VENV_DIR=".venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies if needed
if ! python -c "import fastapi, uvicorn, httpx, bs4, recipe_scrapers" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install --quiet fastapi uvicorn httpx beautifulsoup4 recipe-scrapers
fi

# Get local IP for convenience
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")
echo ""
echo "========================================="
echo "  Recipe Fetcher is running!"
echo "========================================="
echo ""
echo "  On this Mac:  http://localhost:8080"
echo "  On iPad/WiFi: http://${LOCAL_IP}:8080"
echo ""
echo "  Close this window to stop the server"
echo "========================================="
echo ""

# Open Safari after a short delay (server needs a moment to start)
(sleep 2 && open "http://localhost:8080") &

python server.py
