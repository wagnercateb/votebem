#!/usr/bin/env python3
"""
pgAdmin Configuration Helper for VoteBem Development Environment

This script provides the correct connection parameters for pgAdmin to connect to 
the PostgreSQL database running in Docker. It explains the Docker networking 
differences between external connections (DBeaver) and internal connections (pgAdmin).

Usage:
    python config_postgres_admin.py

Requirements:
    - Docker containers must be running (docker-compose -f docker-compose.dev-services.yml up -d)
    - pgAdmin must be accessible at http://localhost:8080
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
            'db_port': config('DB_PORT', default='5432'),
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
            'db_port': '5432',
        }

def check_docker_status():
    """Check if Docker containers are running"""
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True, check=True)
        
        containers = result.stdout
        pgadmin_running = 'votebem_pgadmin_dev' in containers and 'Up' in containers
        postgres_running = 'votebem_db_dev' in containers and 'Up' in containers
        
        return pgadmin_running, postgres_running, containers
    except subprocess.CalledProcessError:
        return False, False, "Docker command failed"

def print_connection_instructions(env_config):
    """Print detailed connection instructions for pgAdmin"""
    print("=" * 70)
    print("📋 PGADMIN CONNECTION INSTRUCTIONS")
    print("=" * 70)
    print()
    
    print("🔗 pgAdmin Access:")
    print(f"   URL: http://localhost:8080")
    print(f"   Email: admin@votebem.dev")
    print(f"   Password: admin123")
    print()
    
    print("🐘 PostgreSQL Connection Parameters for pgAdmin:")
    print("   (Use these EXACT values in pgAdmin)")
    print()
    print(f"   Server Name: VoteBem PostgreSQL (Docker)")
    print(f"   Host: {env_config['db_host_internal']}")
    print(f"   Port: {env_config['db_port']}")
    print(f"   Database: {env_config['db_name']}")
    print(f"   Username: {env_config['db_user']}")
    print(f"   Password: {env_config['db_password']}")
    print(f"   SSL Mode: Prefer")
    print()
    
    print("⚠️  IMPORTANT DIFFERENCES:")
    print("   • pgAdmin (Docker): Use host 'db' (Docker service name)")
    print("   • DBeaver (Windows): Use host 'localhost' (port forwarding)")
    print()
    
    print("📝 Step-by-Step Instructions:")
    print("   1. Open http://localhost:8080 in your browser")
    print("   2. Login with admin@votebem.dev / admin123")
    print("   3. Right-click 'Servers' → 'Register' → 'Server'")
    print("   4. General tab:")
    print("      - Name: VoteBem PostgreSQL (Docker)")
    print("   5. Connection tab:")
    print(f"      - Host name/address: {env_config['db_host_internal']}")
    print(f"      - Port: {env_config['db_port']}")
    print(f"      - Maintenance database: {env_config['db_name']}")
    print(f"      - Username: {env_config['db_user']}")
    print(f"      - Password: {env_config['db_password']}")
    print("   6. Click 'Save'")
    print()
    
    print("🔍 For Comparison - DBeaver Connection:")
    print(f"   Host: {env_config['db_host_external']}")
    print(f"   Port: {env_config['db_port']}")
    print(f"   Database: {env_config['db_name']}")
    print(f"   Username: {env_config['db_user']}")
    print(f"   Password: {env_config['db_password']}")
    print()

def print_troubleshooting():
    """Print troubleshooting information"""
    print("🔧 TROUBLESHOOTING:")
    print()
    print("   If connection fails in pgAdmin:")
    print("   1. Verify containers are running:")
    print("      docker-compose -f docker-compose.dev-services.yml ps")
    print()
    print("   2. Check PostgreSQL logs:")
    print("      docker logs votebem_db_dev")
    print()
    print("   3. Test connection from pgAdmin container:")
    print("      docker exec -it votebem_pgadmin_dev ping db")
    print()
    print("   4. Test PostgreSQL from host:")
    print("      docker exec -it votebem_db_dev psql -U votebem_user -d votebem_dev")
    print()
    print("   5. Restart containers if needed:")
    print("      docker-compose -f docker-compose.dev-services.yml restart")
    print()

def main():
    """Main helper function"""
    print("🐘 VoteBem pgAdmin Configuration Helper")
    print("=" * 70)
    print()
    
    # Load environment configuration
    env_config = load_environment()
    
    # Check Docker status
    pgadmin_running, postgres_running, containers_info = check_docker_status()
    
    print("🐳 Docker Container Status:")
    if pgadmin_running and postgres_running:
        print("   ✅ pgAdmin container: Running")
        print("   ✅ PostgreSQL container: Running")
        print("   ✅ Ready to configure pgAdmin!")
    else:
        print("   ❌ Some containers are not running:")
        if not pgadmin_running:
            print("      - pgAdmin container: Not running")
        if not postgres_running:
            print("      - PostgreSQL container: Not running")
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
    print("✨ After following these instructions, pgAdmin will be able to")
    print("   connect to your PostgreSQL database using Docker networking!")
    print("=" * 70)

if __name__ == "__main__":
    main()