#!/usr/bin/env python3
"""Startup script for Railway deployment"""
import os
import subprocess
import sys

port = os.environ.get("PORT", "8000")
print(f"Starting server on port {port}")

subprocess.run([
    sys.executable, "-m", "uvicorn",
    "api.server:app",
    "--host", "0.0.0.0",
    "--port", port
])
