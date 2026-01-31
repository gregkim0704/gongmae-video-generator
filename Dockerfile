# Dockerfile for Railway deployment
FROM python:3.12-slim

# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p output temp data/input data/mock assets

# Expose port (Railway uses PORT env variable)
EXPOSE ${PORT:-8000}

# Run the API server (use shell form for env variable expansion)
CMD uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}
