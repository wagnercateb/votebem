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
from votebem.utils.devlog import dev_log  # Unified development logging

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
        dev_log(f"Warning: Could not load .env.dev file: {e}")
        dev_log("Using default values...")
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
    dev_log("=" * 70)
    dev_log("📋 ADMINER CONNECTION INSTRUCTIONS")
    dev_log("=" * 70)
    dev_log("")
    
    dev_log("🔗 Adminer Access:")
    dev_log(f"   URL: http://localhost:8080")
    dev_log("")
    
    dev_log("🐬 MariaDB Connection Parameters for Adminer:")
    dev_log("   (Use these EXACT values in Adminer)")
    dev_log("")
    dev_log(f"   System: MySQL")
    dev_log(f"   Server: {env_config['db_host_internal']}")
    dev_log(f"   Port: {env_config['db_port']}")
    dev_log(f"   Database: {env_config['db_name']}")
    dev_log(f"   Username: {env_config['db_user']}")
    dev_log(f"   Password: {env_config['db_password']}")
    dev_log("")
    
    dev_log("⚠️  IMPORTANT DIFFERENCES:")
    dev_log("   • Adminer (Docker): Use server 'db' (Docker service name)")
    dev_log("   • DBeaver (Windows): Use server 'localhost' (port forwarding)")
    dev_log("")
    
    dev_log("📝 Step-by-Step Instructions:")
    dev_log("   1. Open http://localhost:8080 in your browser")
    dev_log("   2. Select System 'MySQL'")
    dev_log(f"   3. Server: {env_config['db_host_internal']}")
    dev_log(f"   4. Username: {env_config['db_user']}")
    dev_log(f"   5. Password: {env_config['db_password']}")
    dev_log(f"   6. Database: {env_config['db_name']}")
    dev_log("   7. Click 'Login'")
    dev_log("")
    
    dev_log("🔍 For Comparison - DBeaver Connection:")
    dev_log(f"   Server: {env_config['db_host_external']}")
    dev_log(f"   Port: {env_config['db_port']}")
    dev_log(f"   Database: {env_config['db_name']}")
    dev_log(f"   Username: {env_config['db_user']}")
    dev_log(f"   Password: {env_config['db_password']}")
    dev_log("")

def print_troubleshooting():
    """Print troubleshooting information"""
    dev_log("🔧 TROUBLESHOOTING:")
    dev_log("")
    dev_log("   If connection fails in Adminer:")
    dev_log("   1. Verify containers are running:")
    dev_log("      docker-compose -f docker-compose.dev-services.yml ps")
    dev_log("")
    dev_log("   2. Check MariaDB logs:")
    dev_log("      docker logs votebem_db_dev")
    dev_log("")
    dev_log("   3. Test connection from Adminer container:")
    dev_log("      docker exec -it votebem_adminer_dev ping db")
    dev_log("")
    dev_log("   4. Test MariaDB from host:")
    dev_log("      docker exec -it votebem_db_dev mysql -u votebem_user -p$MARIADB_PASSWORD -D votebem_dev -h 127.0.0.1 -P 3306")
    dev_log("")
    dev_log("   5. Restart containers if needed:")
    dev_log("      docker-compose -f docker-compose.dev-services.yml restart")
    dev_log("")

def main():
    """Main helper function"""
    dev_log("🐬 VoteBem Adminer Configuration Helper")
    dev_log("=" * 70)
    dev_log("")
    
    # Load environment configuration
    env_config = load_environment()
    
    # Check Docker status
    adminer_running, mariadb_running, containers_info = check_docker_status()
    
    dev_log("🐳 Docker Container Status:")
    if adminer_running and mariadb_running:
        dev_log("   ✅ Adminer container: Running")
        dev_log("   ✅ MariaDB container: Running")
        dev_log("   ✅ Ready to configure Adminer!")
    else:
        dev_log("   ❌ Some containers are not running:")
        if not adminer_running:
            dev_log("      - Adminer container: Not running")
        if not mariadb_running:
            dev_log("      - MariaDB container: Not running")
        dev_log("")
        dev_log("   🚀 Start containers with:")
        dev_log("      docker-compose -f docker-compose.dev-services.yml up -d")
        dev_log("")
        return

    dev_log("")
    
    # Print connection instructions
    print_connection_instructions(env_config)
    
    # Print troubleshooting
    print_troubleshooting()
    
    dev_log("=" * 70)
    dev_log("✨ After following these instructions, Adminer will be able to")
    dev_log("   connect to your MariaDB database using Docker networking!")
    dev_log("=" * 70)

if __name__ == "__main__":
    main()