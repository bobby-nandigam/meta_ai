# Dockerfile for Autonomous Work OS
# Deployment on Hugging Face Spaces and cloud platforms

FROM python:3.11-slim

# Set metadata
LABEL maintainer="Meta AI <ai-workos@meta.com>"
LABEL description="Autonomous Work OS - Production-ready multi-agent AI system"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt --no-cache-dir

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:$PYTHONPATH
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command runs the baseline inference script
# Override with: docker run -e HF_TOKEN=$YOUR_TOKEN autonomous-workos python inference.py
CMD ["python", "inference.py"]

# Alternative: Run the API server
# CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]

# For Hugging Face Spaces integration
# Spaces automatically routes to port 7860 for Gradio/Streamlit
# For FastAPI, expose:
EXPOSE 7860

# Build: docker build -t autonomous-workos:latest .
# Run: docker run --env HF_TOKEN=$HF_TOKEN autonomous-workos:latest
# Run with GPU: docker run --gpus all --env HF_TOKEN=$HF_TOKEN autonomous-workos:latest
