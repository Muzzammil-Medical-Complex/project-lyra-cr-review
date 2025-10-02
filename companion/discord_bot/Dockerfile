# Use the official Python image as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG DISCORD_BOT_PORT=8001
ENV DISCORD_BOT_PORT=${DISCORD_BOT_PORT}

# Set the working directory
WORKDIR /root_app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code as a package
COPY . /root_app/discord_bot/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /root_app
USER appuser

# Expose port if needed for health checks (though Discord bots typically don't expose HTTP)
EXPOSE ${DISCORD_BOT_PORT}

# Run the application
CMD ["python", "-m", "discord_bot.bot"]
