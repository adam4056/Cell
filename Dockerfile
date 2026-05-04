# Cell-2 Docker Image
# Usage:
#   docker build -t cell2 .
#   docker run -it --rm -v cell2-data:/app/data cell2
#   docker run -it --rm -v cell2-data:/app/data -e CELL_API_KEY=sk-xxx cell2

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for persistent data
RUN mkdir -p /app/data/memory /app/data/brain/functions /app/data/brain/backup

# Expose port for HTTP API (future)
EXPOSE 8080

# Environment variables
ENV CELL_CONFIG_PATH=/app/data/config.yaml
ENV CELL_CONTEXT_PATH=/app/data/context.json
ENV CELL_MEMORY_PATH=/app/data/memory
ENV CELL_BRAIN_PATH=/app/data/brain
ENV PYTHONUNBUFFERED=1

# Copy and set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py"]
