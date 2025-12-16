#!/bin/bash

# ==============================================================================
# Script to verify Votebem Web Container Infrastructure (Redis + ChromaDB)
# Run this script on the HOST machine (where docker-compose is running).
# usage: ./check_infra_container.sh
# ==============================================================================

CONTAINER_NAME="votebem-web"

# Ensure container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ ERROR: Container '$CONTAINER_NAME' is not running."
    echo "Current running containers:"
    docker ps
    exit 1
fi

echo "✅ Found container '$CONTAINER_NAME'."
echo "🚀 Executing diagnostic script inside the container..."
echo "=============================================================================="

# Run Python diagnostics inside the Django environment
docker exec -i "$CONTAINER_NAME" python manage.py shell << 'EOF'
import sys
import os
import time
import traceback
import platform

def print_header(msg):
    print(f"\n{'-'*80}")
    print(f" {msg}")
    print(f"{'-'*80}")

def check_user_perms(path):
    """Check if current user has write permissions to path"""
    try:
        import pwd
        user = pwd.getpwuid(os.getuid()).pw_name
    except:
        user = str(os.getuid())
        
    print(f"[*] Current Process User: {user} (UID: {os.getuid()}, GID: {os.getgid()})")
    
    if not path:
        return
        
    if os.path.exists(path):
        stats = os.stat(path)
        print(f"[*] Path '{path}' exists.")
        print(f"    - Owner UID: {stats.st_uid}, GID: {stats.st_gid}")
        print(f"    - Permissions: {oct(stats.st_mode)[-3:]}")
        
        if os.access(path, os.W_OK):
            print(f"    - [OK] Writable by current user.")
        else:
            print(f"    - [WARNING] NOT Writable by current user.")
    else:
        print(f"[*] Path '{path}' does not exist.")
        parent = os.path.dirname(path)
        if parent and os.path.exists(parent):
             print(f"    - Checking parent: {parent}")
             check_user_perms(parent)

def check_redis():
    print_header("DIAGNOSIS: REDIS (VALKEY)")
    try:
        from django.conf import settings
        redis_url = getattr(settings, 'REDIS_URL', os.environ.get('REDIS_URL'))
        print(f"[*] REDIS_URL from settings: {redis_url}")
        
        if not redis_url:
            print("[❌] ERROR: No REDIS_URL configured.")
            return False

        import redis
        # Set short timeout for test
        r = redis.from_url(redis_url, socket_timeout=3)
        
        print("[*] Pinging Redis...")
        try:
            if r.ping():
                print("[✅] Redis PING successful.")
        except Exception as e:
            print(f"[❌] Redis PING FAILED: {e}")
            print("    -> Check if 'valkey' service is running and network is shared.")
            return False
            
        print("[*] Testing Write/Read...")
        try:
            r.set('infra_test_key', 'ok', ex=10)
            val = r.get('infra_test_key')
            if val == b'ok':
                print("[✅] Redis Read/Write successful.")
                return True
            else:
                print(f"[❌] Redis Read mismatch: got {val}")
                return False
        except Exception as e:
            print(f"[❌] Redis Write/Read ERROR: {e}")
            return False

    except ImportError:
        print("[❌] 'redis' library not installed.")
    except Exception as e:
        print(f"[❌] Unexpected Redis Error: {e}")
        traceback.print_exc()
    return False

def check_chroma():
    print_header("DIAGNOSIS: CHROMADB")
    
    try:
        from django.conf import settings
        # 1. Check Settings
        persist_path = getattr(settings, 'CHROMA_PERSIST_PATH', '')
        print(f"[*] CHROMA_PERSIST_PATH: '{persist_path}'")
        
        if not persist_path:
             print("[!] WARNING: CHROMA_PERSIST_PATH is not set. Chroma will run in-memory (data lost on restart).")
        
        # 2. Check Permissions
        check_user_perms(persist_path)
        
        # 3. Import Check
        print("[*] Importing chromadb...")
        import chromadb
        print(f"[*] ChromaDB Version: {chromadb.__version__}")
        
        # 4. Client Initialization
        print("[*] Initializing Client...")
        try:
            if persist_path:
                client = chromadb.PersistentClient(path=persist_path)
            else:
                client = chromadb.Client()
            print("[✅] Client initialized successfully.")
        except Exception as e:
            print(f"[❌] FAILED to initialize Chroma Client: {e}")
            print("    -> Common causes: SQLite version mismatch, file permissions, or corrupt database.")
            return False

        # 5. Operational Check
        print("[*] Listing collections...")
        try:
            colls = client.list_collections()
            names = [c.name for c in colls]
            print(f"[*] Found {len(names)} collections: {names}")
            
            # Try a dummy heartbeat query or embedding if needed
            print("[✅] ChromaDB seems operational.")
            return True
        except Exception as e:
            print(f"[❌] FAILED to list collections: {e}")
            return False

    except ImportError:
        print("[❌] 'chromadb' library not installed.")
    except Exception as e:
        print(f"[❌] Unexpected ChromaDB Error: {e}")
        traceback.print_exc()
    return False

def main():
    print(f"[*] Python: {platform.python_version()}")
    print(f"[*] CWD: {os.getcwd()}")
    
    redis_ok = check_redis()
    chroma_ok = check_chroma()
    
    print_header("SUMMARY")
    if redis_ok:
        print("Redis:    [PASS] ✅")
    else:
        print("Redis:    [FAIL] ❌")
        
    if chroma_ok:
        print("ChromaDB: [PASS] ✅")
    else:
        print("ChromaDB: [FAIL] ❌")

    if not (redis_ok and chroma_ok):
        sys.exit(1)

main()
EOF

if [ $? -eq 0 ]; then
    echo "=============================================================================="
    echo "✅ INFRASTRUCTURE CHECK PASSED"
else
    echo "=============================================================================="
    echo "❌ INFRASTRUCTURE CHECK FAILED"
fi
