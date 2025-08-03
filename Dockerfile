FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y curl git ca-certificates --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY . .

# Install Python dependencies
RUN uv sync

# Create directories
RUN mkdir -p /app/data /app/logs /app/output

# Volumes
VOLUME ["/app/data", "/app/logs", "/app/output"]

# Default command
CMD ["uv", "run", "python", "src/main.py"]