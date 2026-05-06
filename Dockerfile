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

# Expose port
EXPOSE 8000

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV CONTAINER_ENV=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run the ASGI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
