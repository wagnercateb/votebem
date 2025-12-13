#!/bin/bash

#==============================================================================
# Generic Project Docker Update Script
#==============================================================================
# PURPOSE:
#   Update a project's web service container after pulling the latest code.
#   Steps:
#     1) Prompt for project name (default: 'votebem')
#     2) cd into /dados/<project>
#     3) git pull
#     4) Stop the project's containers
#     5) Rebuild the images
#     6) Restart (recreate) containers
#
# USAGE:
#   ./update_project_container.sh
#
# REQUIREMENTS:
#   - Project directory exists at /dados/<project>
#   - Git repository initialized in that directory
#   - docker-compose.yml (or compose.yaml) present
#   - Docker and Compose v2 installed (fallback to Compose v1 if available)
#
# NOTES:
#   - This script targets the whole project stack. If you need a single
#     service restart, you can edit SERVICE filtering logic below.
#   - Uses defensive checks and provides informative output throughout.
#   - Avoids command chaining (&&); runs steps sequentially for clarity.
#
# AUTHOR: Ops Toolkit
# VERSION: 1.0
# LAST MODIFIED: 2025-11-30
#==============================================================================

set -e

echo "=== Project Docker Update ==="

#------------------------------------------------------------------------------
# Prompt for project name (default: votebem)
#------------------------------------------------------------------------------
read -r -p "Project name [votebem]: " PROJECT_INPUT
if [ -z "$PROJECT_INPUT" ]; then
  PROJECT="votebem"
else
  PROJECT="$PROJECT_INPUT"
fi
echo "Selected project: $PROJECT"

#------------------------------------------------------------------------------
# Resolve project directory
#------------------------------------------------------------------------------
PROJECT_DIR="/dados/$PROJECT"
echo "Target directory: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Error: Directory '$PROJECT_DIR' not found."
  echo "Ensure the project is deployed at /dados/$PROJECT or choose the correct name."
  exit 1
fi

#------------------------------------------------------------------------------
# Change into project directory
#------------------------------------------------------------------------------
cd "$PROJECT_DIR"

#------------------------------------------------------------------------------
# Verify git repository and pull latest
#------------------------------------------------------------------------------
if [ -d ".git" ]; then
  echo "Pulling latest changes from git..."
  git fetch --all
  git pull --ff-only
else
  echo "Warning: No git repository detected in '$PROJECT_DIR'. Skipping git pull."
fi

#------------------------------------------------------------------------------
# Determine docker compose command (v2 vs v1)
#------------------------------------------------------------------------------
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    echo "Error: Neither 'docker compose' (v2) nor 'docker-compose' (v1) is available."
    echo "Install Docker Compose and retry."
    exit 1
  fi
fi
echo "Using Compose command: $COMPOSE_CMD"

#------------------------------------------------------------------------------
# Check compose file presence
#------------------------------------------------------------------------------
COMPOSE_FILE="docker-compose.yml"
ALT_COMPOSE_FILE="compose.yaml"

if [ -f "$COMPOSE_FILE" ]; then
  echo "Compose file found: $COMPOSE_FILE"
elif [ -f "$ALT_COMPOSE_FILE" ]; then
  echo "Compose file found: $ALT_COMPOSE_FILE"
  COMPOSE_FILE="$ALT_COMPOSE_FILE"
else
  echo "Error: No compose file found (docker-compose.yml or compose.yaml)."
  exit 1
fi

#------------------------------------------------------------------------------
# Stop existing containers for the project
#------------------------------------------------------------------------------
echo "Stopping containers (down)..."
$COMPOSE_CMD -f "$COMPOSE_FILE" down

#------------------------------------------------------------------------------
# Rebuild images
#------------------------------------------------------------------------------
echo "Rebuilding images (build, no-cache, pull base)..."
# Use --no-cache to avoid stale layers; --pull to refresh base images
$COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache --pull

# Optional: prune dangling images left from previous builds to reclaim disk space
echo "Pruning dangling images (safe cleanup)..."
docker image prune -f || true

#------------------------------------------------------------------------------
# Restart containers in detached mode
#------------------------------------------------------------------------------
echo "Starting containers (up -d --force-recreate)..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d --force-recreate --remove-orphans

# Show resulting image sizes for visibility (non-fatal if docker changes output)
echo "Current image sizes (filtered)..."
docker images | grep -E "mariadb|valkey|votebem-web" || true

#------------------------------------------------------------------------------
# Show service list and tail logs briefly to confirm
#------------------------------------------------------------------------------
echo "Services in stack:"
$COMPOSE_CMD -f "$COMPOSE_FILE" config --services || true

echo "Showing recent logs (5 seconds)..."
($COMPOSE_CMD -f "$COMPOSE_FILE" logs --since=5s || true) | tail -n 200

echo "=== Update complete for project '$PROJECT' ==="
