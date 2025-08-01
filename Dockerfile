FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y nodejs npm curl git ca-certificates --no-install-recommends \
    && npm install -g npx \
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

# Install ArXiv MCP server properly
RUN uv tool install arxiv-mcp-server

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Create directories
RUN mkdir -p /app/data /app/logs /app/output

# Volumes
VOLUME ["/app/data", "/app/logs", "/app/output"]

# Default command
CMD ["uv", "run", "python", "src/main.py"]