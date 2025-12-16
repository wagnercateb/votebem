#!/bin/bash

# ==============================================================================
# Script to fix permission issues for Votebem Docker Containers
# Run this script on the HOST machine with sudo.
# usage: sudo ./fix_docker_permissions.sh
# ==============================================================================

# The User ID used inside the container (defined in Dockerfile as 'appuser')
# In standard python:slim images + adduser, this is usually 1000.
CONTAINER_UID=1000
CONTAINER_GID=1000

echo "🔧 Fixing permissions for Votebem volumes..."
echo "Target UID: $CONTAINER_UID, Target GID: $CONTAINER_GID"
echo "--------------------------------------------------------"

# List of directories that the container needs to WRITE to.
# Based on docker-compose.yml volumes and application settings.
DIRS_TO_FIX=(
    "/dados/embeddings/votebem"         # ChromaDB persistence
    "/dados/votebem/logs"               # Application logs
    "/dados/votebem/votebem/media"      # User uploaded media
    "/dados/votebem/docs/respostas_ia"  # RAG generated answers
    "/dados/votebem/docs/noticias"      # News for embedding
    "/dados/chroma"                     # Optional chroma mount
)

for DIR in "${DIRS_TO_FIX[@]}"; do
    if [ -d "$DIR" ]; then
        echo "Processing: $DIR"
        
        # Change ownership to container user
        chown -R $CONTAINER_UID:$CONTAINER_GID "$DIR"
        
        # Ensure standard permissions (Owner: RWX, Group: RX, Others: RX)
        # You can change to 775 if you want group write access.
        chmod -R 755 "$DIR"
        
        echo "  ✅ Ownership set to $CONTAINER_UID:$CONTAINER_GID"
    else
        echo "⚠️  Directory not found (skipping): $DIR"
        # Optional: Create if it should exist
        # mkdir -p "$DIR" && chown -R $CONTAINER_UID:$CONTAINER_GID "$DIR"
    fi
done

echo "--------------------------------------------------------"
echo "✅ Permissions update complete."
echo "PLEASE RESTART THE CONTAINER:"
echo "  docker compose restart web"
