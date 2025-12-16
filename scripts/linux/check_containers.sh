#!/bin/bash

# Script to check web container communication with ChromaDB and Redis
# Usage: ./check_containers.sh
# Run this from the project root or scripts directory

# Define paths (adjust relative to script location)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="$PROJECT_ROOT/.env"
DOCKERFILE="$PROJECT_ROOT/Dockerfile"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

echo "========================================================"
echo "      VotoBem Container Diagnostic Script"
echo "========================================================"
echo "Project Root: $PROJECT_ROOT"
echo "Date: $(date)"
echo "--------------------------------------------------------"

# 1. Check Configuration Files
echo "[1] Checking Configuration Files..."

if [ -f "$ENV_FILE" ]; then
    echo "  [OK] .env found."
    # Check key variables
    if grep -q "REDIS_URL" "$ENV_FILE"; then
        echo "       REDIS_URL is present."
    else
        echo "       [WARNING] REDIS_URL missing in .env"
    fi
    if grep -q "CHROMA_PERSIST_PATH" "$ENV_FILE"; then
        echo "       CHROMA_PERSIST_PATH is present."
    else
        echo "       [WARNING] CHROMA_PERSIST_PATH missing in .env"
    fi
else
    echo "  [ERROR] .env NOT found at $ENV_FILE"
fi

if [ -f "$DOCKERFILE" ]; then
    echo "  [OK] Dockerfile found."
else
    echo "  [ERROR] Dockerfile NOT found at $DOCKERFILE"
fi

if [ -f "$COMPOSE_FILE" ]; then
    echo "  [OK] docker-compose.yml found."
    # Validate compose file syntax
    echo "  Validating compose file syntax..."
    if $DOCKER_COMPOSE -f "$COMPOSE_FILE" config > /dev/null 2>&1; then
        echo "  [OK] docker-compose.yml syntax is valid."
    else
        echo "  [ERROR] docker-compose.yml syntax is INVALID."
        $DOCKER_COMPOSE -f "$COMPOSE_FILE" config
    fi
else
    echo "  [ERROR] docker-compose.yml NOT found at $COMPOSE_FILE"
fi

echo "--------------------------------------------------------"

# 2. Check Running Containers
echo "[2] Checking Running Containers..."

WEB_CONTAINER=$($DOCKER_COMPOSE -f "$COMPOSE_FILE" ps -q web)
REDIS_CONTAINER=$($DOCKER_COMPOSE -f "$COMPOSE_FILE" ps -q valkey)

if [ -z "$WEB_CONTAINER" ]; then
    echo "  [ERROR] Web container is NOT running."
else
    echo "  [OK] Web container is running (ID: ${WEB_CONTAINER:0:12})"
fi

if [ -z "$REDIS_CONTAINER" ]; then
    echo "  [ERROR] Valkey (Redis) container is NOT running."
else
    echo "  [OK] Valkey container is running (ID: ${REDIS_CONTAINER:0:12})"
fi

echo "--------------------------------------------------------"

# 3. Test Redis Connectivity from Web Container
echo "[3] Testing Redis Connectivity from Web Container..."

if [ -n "$WEB_CONTAINER" ]; then
    # We use python to test redis connection because redis-cli might not be in the web image
    echo "  Running Python redis test..."
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" exec -T web python -c "
import os
import redis
import sys

try:
    from decouple import config
    redis_url = os.environ.get('REDIS_URL') or config('REDIS_URL', default='redis://valkey:6379/0')
    print(f'  Connecting to: {redis_url}')
    r = redis.from_url(redis_url)
    r.ping()
    print('  [SUCCESS] Redis PING successful.')
except Exception as e:
    print(f'  [FAILURE] Redis connection failed: {e}')
    sys.exit(1)
"
    if [ $? -eq 0 ]; then
        echo "  Redis test passed."
    else
        echo "  Redis test FAILED."
    fi
else
    echo "  [SKIP] Web container not running."
fi

echo "--------------------------------------------------------"

# 4. Test ChromaDB Connectivity/Persistence from Web Container
echo "[4] Testing ChromaDB Connectivity from Web Container..."

if [ -n "$WEB_CONTAINER" ]; then
    echo "  Running Python ChromaDB test..."
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" exec -T web python -c "
import os
import sys
try:
    import chromadb
    from decouple import config
    
    persist_path = os.environ.get('CHROMA_PERSIST_PATH') or config('CHROMA_PERSIST_PATH', default='')
    print(f'  Chroma Persist Path: {persist_path}')
    
    if persist_path:
        try:
            client = chromadb.PersistentClient(path=persist_path)
            print('  [SUCCESS] PersistentClient created.')
        except Exception as e:
            print(f'  [FAILURE] Could not create PersistentClient: {e}')
            sys.exit(1)
    else:
        print('  [INFO] Using ephemeral Client (no persistence configured).')
        client = chromadb.Client()

    try:
        hb = client.heartbeat()
        print(f'  [SUCCESS] Chroma Heartbeat: {hb}')
        
        # List collections
        colls = client.list_collections()
        names = [c.name for c in colls]
        print(f'  Collections found: {names}')
        
    except Exception as e:
        print(f'  [FAILURE] Chroma operation failed: {e}')
        sys.exit(1)

except ImportError:
    print('  [FAILURE] chromadb library not installed.')
    sys.exit(1)
except Exception as e:
    print(f'  [FAILURE] Unexpected error: {e}')
    sys.exit(1)
"
    if [ $? -eq 0 ]; then
        echo "  ChromaDB test passed."
    else
        echo "  ChromaDB test FAILED."
    fi
else
    echo "  [SKIP] Web container not running."
fi

echo "========================================================"
echo "Diagnostic Complete."
