#!/bin/sh
set -e

# Create data directories if they don't exist
mkdir -p /app/data/memory/core /app/data/memory/semantic /app/data/memory/episodic /app/data/memory/procedural
mkdir -p /app/data/brain/functions /app/data/brain/backup

# Copy default config if none exists
if [ ! -f /app/data/config.yaml ]; then
    cp /app/config.yaml /app/data/config.yaml
fi

# Run the application
exec python main.py "$@"
