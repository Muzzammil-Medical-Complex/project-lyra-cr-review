# Use the official Python image as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app_root

ARG GATEWAY_HOST=0.0.0.0
ARG GATEWAY_PORT=8000
ENV GATEWAY_HOST=${GATEWAY_HOST} \
    GATEWAY_PORT=${GATEWAY_PORT}

# Set the working directory
WORKDIR /app_root

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code as a package
COPY . /app_root/gateway/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app_root
USER appuser

# Expose the port the app runs on
EXPOSE ${GATEWAY_PORT}

# Run the application
CMD ["sh", "-c", "python -m uvicorn gateway.main:app --host ${GATEWAY_HOST:-0.0.0.0} --port ${GATEWAY_PORT:-8000}"]
