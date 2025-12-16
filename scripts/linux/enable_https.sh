#!/bin/bash
# Script to enable HTTPS mode in Django .env
# This ensures USE_HTTPS=True is set, which activates secure cookies and redirects.

ENV_FILE="/dados/votebem/.env"
COMPOSE_FILE="/dados/votebem/docker-compose.prod.yml"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
  echo "Please run as root (sudo)"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

echo "Updating $ENV_FILE..."

# Update or append USE_HTTPS=True
if grep -q "^USE_HTTPS=" "$ENV_FILE"; then
    sed -i 's/^USE_HTTPS=.*/USE_HTTPS=True/' "$ENV_FILE"
    echo "Updated existing USE_HTTPS to True"
else
    echo "USE_HTTPS=True" >> "$ENV_FILE"
    echo "Appended USE_HTTPS=True"
fi

# Also ensure ALLOWED_HOSTS includes the domain if not present (optional safety)
# (Skipping complex logic here, assuming user has it set up)

echo "Restarting web container to apply settings..."
if [ -f "$COMPOSE_FILE" ]; then
    docker compose -f "$COMPOSE_FILE" restart web
else
    # Fallback if file not found (maybe relative path)
    docker compose restart web
fi

echo "Done! HTTPS mode enabled."
