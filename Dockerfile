# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy Python files and requirements
COPY pyproject.toml README.md requirements.txt ./
COPY *.py ./
COPY providers/ ./providers/
COPY models/ ./models/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install ASGI server
RUN pip install --no-cache-dir uvicorn[standard]

# Install the package in development mode
RUN pip install --no-cache-dir -e .

# Expose port (documentation only; Cloud Run injects its own PORT)
EXPOSE 8000

# Set environment variables
# NOTE: PORT is intentionally NOT set here. Cloud Run injects PORT at runtime
# (usually 8080). Local/Fly runs fall back to 8000 via ${PORT:-8000} below.
ENV PYTHONUNBUFFERED=1
ENV CONTAINER_ENV=1
# Ensure root-level modules (borsa_models, borsa_client, etc.) are importable when
# uvicorn runs as a console script — the editable install's finder doesn't reliably
# expose top-level py-modules, and /app isn't otherwise on sys.path.
ENV PYTHONPATH=/app

# Health check (honored by local Docker/Fly; Cloud Run ignores this and probes
# the container PORT directly). Uses ${PORT:-8000} to match the runtime port.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os,httpx; httpx.get(f\"http://localhost:{os.getenv('PORT','8000')}/health\", timeout=5)" || exit 1

# Run the ASGI application (shell form so ${PORT} expands at container start).
# --proxy-headers + --forwarded-allow-ips='*' make uvicorn trust X-Forwarded-Proto
# from the reverse proxy (Coolify/Dokploy Traefik, Caddy, Cloud Run), so FastMCP
# emits https URLs and the /mcp/ -> http:// redirect-downgrade can't happen.
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
