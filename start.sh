#!/bin/bash
# Start script for Railway deployment

# Use PORT from environment, default to 8000
PORT="${PORT:-8000}"

echo "Starting server on port $PORT"

exec uvicorn api.server:app --host 0.0.0.0 --port "$PORT"
