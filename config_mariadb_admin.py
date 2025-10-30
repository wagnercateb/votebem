#!/usr/bin/env python3
"""
Adminer Configuration Helper for VoteBem Development Environment

This script provides the correct connection parameters for Adminer to connect to 
the MariaDB database running in Docker. It explains the Docker networking 
differences between external connections (DBeaver) and internal connections (Adminer).

Usage:
    python config_mariadb_admin.py

Requirements:
    - Docker containers must be running (docker-compose -f docker-compose.dev-services.yml up -d)
    - Adminer must be accessible at http://localhost:8080
"""

import sys
import os
import subprocess
from decouple import Config, RepositoryEnv

def load_environment():
    """Load environment variables from .env.dev file"""
    try:
        config = Config(RepositoryEnv('.env.dev'))
        return {
            'db_name': config('DB_NAME', default='votebem_dev'),
            'db_user': config('DB_USER', default='votebem_user'),
            'db_password': config('DB_PASSWORD', default='votebem_dev_password'),
            'db_host_internal': 'db',  # Docker service name
            'db_host_external': 'localhost',  # For external connections
            'db_port': config('DB_PORT', default='3306'),
        }
    except Exception as e:
        print(f"Warning: Could not load .env.dev file: {e}")
        print("Using default values...")
        return {
            'db_name': 'votebem_dev',
            'db_user': 'votebem_user',
            'db_password': 'votebem_dev_password',
            'db_host_internal': 'db',
            'db_host_external': 'localhost',
            'db_port': '3306',
        }

def check_docker_status():
    """Check if Docker containers are running"""
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True, check=True)
        
        containers = result.stdout
        adminer_running = 'votebem_adminer_dev' in containers and 'Up' in containers
        mariadb_running = 'votebem_db_dev' in containers and 'Up' in containers

        return adminer_running, mariadb_running, containers
    except subprocess.CalledProcessError:
        return False, False, "Docker command failed"

def print_connection_instructions(env_config):
    """Print detailed connection instructions for Adminer"""
    print("=" * 70)
    print("📋 ADMINER CONNECTION INSTRUCTIONS")
    print("=" * 70)
    print()
    
    print("🔗 Adminer Access:")
    print(f"   URL: http://localhost:8080")
    print()
    
    print("🐬 MariaDB Connection Parameters for Adminer:")
    print("   (Use these EXACT values in Adminer)")
    print()
    print(f"   System: MySQL")
    print(f"   Server: {env_config['db_host_internal']}")
    print(f"   Port: {env_config['db_port']}")
    print(f"   Database: {env_config['db_name']}")
    print(f"   Username: {env_config['db_user']}")
    print(f"   Password: {env_config['db_password']}")
    print()
    
    print("⚠️  IMPORTANT DIFFERENCES:")
    print("   • Adminer (Docker): Use server 'db' (Docker service name)")
    print("   • DBeaver (Windows): Use server 'localhost' (port forwarding)")
    print()
    
    print("📝 Step-by-Step Instructions:")
    print("   1. Open http://localhost:8080 in your browser")
    print("   2. Select System 'MySQL'")
    print(f"   3. Server: {env_config['db_host_internal']}")
    print(f"   4. Username: {env_config['db_user']}")
    print(f"   5. Password: {env_config['db_password']}")
    print(f"   6. Database: {env_config['db_name']}")
    print("   7. Click 'Login'")
    print()
    
    print("🔍 For Comparison - DBeaver Connection:")
    print(f"   Server: {env_config['db_host_external']}")
    print(f"   Port: {env_config['db_port']}")
    print(f"   Database: {env_config['db_name']}")
    print(f"   Username: {env_config['db_user']}")
    print(f"   Password: {env_config['db_password']}")
    print()

def print_troubleshooting():
    """Print troubleshooting information"""
    print("🔧 TROUBLESHOOTING:")
    print()
    print("   If connection fails in Adminer:")
    print("   1. Verify containers are running:")
    print("      docker-compose -f docker-compose.dev-services.yml ps")
    print()
    print("   2. Check MariaDB logs:")
    print("      docker logs votebem_db_dev")
    print()
    print("   3. Test connection from Adminer container:")
    print("      docker exec -it votebem_adminer_dev ping db")
    print()
    print("   4. Test MariaDB from host:")
    print("      docker exec -it votebem_db_dev mysql -u votebem_user -p$MARIADB_PASSWORD -D votebem_dev -h 127.0.0.1 -P 3306")
    print()
    print("   5. Restart containers if needed:")
    print("      docker-compose -f docker-compose.dev-services.yml restart")
    print()

def main():
    """Main helper function"""
    print("🐬 VoteBem Adminer Configuration Helper")
    print("=" * 70)
    print()
    
    # Load environment configuration
    env_config = load_environment()
    
    # Check Docker status
    adminer_running, mariadb_running, containers_info = check_docker_status()
    
    print("🐳 Docker Container Status:")
    if adminer_running and mariadb_running:
        print("   ✅ Adminer container: Running")
        print("   ✅ MariaDB container: Running")
        print("   ✅ Ready to configure Adminer!")
    else:
        print("   ❌ Some containers are not running:")
        if not adminer_running:
            print("      - Adminer container: Not running")
        if not mariadb_running:
            print("      - MariaDB container: Not running")
        print()
        print("   🚀 Start containers with:")
        print("      docker-compose -f docker-compose.dev-services.yml up -d")
        print()
        return
    
    print()
    
    # Print connection instructions
    print_connection_instructions(env_config)
    
    # Print troubleshooting
    print_troubleshooting()
    
    print("=" * 70)
    print("✨ After following these instructions, Adminer will be able to")
    print("   connect to your MariaDB database using Docker networking!")
    print("=" * 70)

if __name__ == "__main__":
    main()