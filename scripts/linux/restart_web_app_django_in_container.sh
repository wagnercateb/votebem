#!/bin/bash
# Script to restart the votebem-web container by recreating it
# This ensures environment variables from .env are reloaded.

# Define paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

# Function to determine docker compose command
docker_compose_cmd() {
    if docker compose version &> /dev/null; then
        docker compose "$@"
    elif docker-compose version &> /dev/null; then
        docker-compose "$@"
    else
        echo "Error: Neither 'docker compose' nor 'docker-compose' found." >&2
        return 1
    fi
}

echo "Restarting 'web' service using Docker Compose..."
echo "Project Root: $PROJECT_ROOT"
echo "Compose File: $COMPOSE_FILE"

# Recreate the container to pick up .env changes
docker_compose_cmd -f "$COMPOSE_FILE" up -d --force-recreate web

if [ $? -eq 0 ]; then
    echo "Container recreated successfully."
    echo "Current status:"
    docker_compose_cmd -f "$COMPOSE_FILE" ps web
else
    echo "Failed to recreate container."
    exit 1
fi
