#!/bin/bash
set -e

# Resolve project root
# This script is expected to be in scripts/linux/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
NGINX_CONF_DIR="$PROJECT_ROOT/nginx"
STATIC_DIR="$PROJECT_ROOT/static"
MAINTENANCE_FILE="$STATIC_DIR/maintenance.html"

echo "=== Setting up Maintenance Page for VoteBem ==="
echo "Project Root: $PROJECT_ROOT"

# 1. Verify maintenance.html existence
if [ ! -f "$MAINTENANCE_FILE" ]; then
    echo "Error: maintenance.html not found in $STATIC_DIR"
    echo "Please create the file first."
    exit 1
fi
echo "Found maintenance.html"

# 2. Update Nginx configurations (default.conf and production.conf)
CONFIG_FILES=("default.conf" "production.conf")

for FILE in "${CONFIG_FILES[@]}"; do
    CONF_PATH="$NGINX_CONF_DIR/$FILE"
    if [ -f "$CONF_PATH" ]; then
        echo "Processing $FILE..."
        
        # Check if error_page is already defined
        if grep -q "error_page 502" "$CONF_PATH"; then
            echo "  - Maintenance page already configured in $FILE."
        else
            # Insert error_page directive before 'location /static/'
            # We use sed to insert the line.
            # The pattern looks for "location /static/ {" and inserts the error_page directive before it.
            sed -i '/location \/static\/ {/i \    # Custom Error Page for Maintenance/Offline\n    error_page 502 503 504 /static/maintenance.html;\n' "$CONF_PATH"
            echo "  - Added error_page directive to $FILE."
        fi
    else
        echo "Warning: $CONF_PATH not found."
    fi
done

# 3. Update running container
# We need to put the maintenance file into the volume where /static/ is served.
# In the Nginx container, /static/ is aliased to /app/staticfiles/
# So we need to put maintenance.html into /app/staticfiles/maintenance.html

if command -v docker >/dev/null 2>&1 && docker ps | grep -q votebem_nginx; then
    echo "Updating running Nginx container..."
    
    # Copy maintenance.html to container
    # This places it in the volume mounted at /app/staticfiles
    if docker cp "$MAINTENANCE_FILE" votebem_nginx:/app/staticfiles/maintenance.html; then
        echo "  - Copied maintenance.html to container static folder."
        
        # Reload Nginx to pick up config changes (if the config file mount is live)
        # Note: If default.conf is mounted from the host, changes to the host file should be visible.
        if docker exec votebem_nginx nginx -s reload; then
            echo "  - Nginx reloaded successfully."
        else
            echo "  - Failed to reload Nginx."
        fi
    else
        echo "  - Failed to copy maintenance.html to container."
    fi
else
    echo "Nginx container (votebem_nginx) is not running."
    echo "Configuration files have been updated."
    echo "When you start the stack, ensure 'collectstatic' runs or the maintenance file is present in the static volume."
    echo "You can manually copy it later with: docker cp static/maintenance.html votebem_nginx:/app/staticfiles/"
fi

# 4. Check for Host Nginx (VPS)
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet nginx; then
        echo ""
        echo "=== Host Nginx Detected ==="
        echo "It appears Nginx is running directly on this VPS."
        echo "To apply changes and restart Host Nginx:"
        echo "  sudo systemctl restart nginx"
        echo ""
        echo "Note: Ensure 'maintenance.html' is in your host's static file directory."
        echo "      (e.g., /opt/votebem/static/ or /var/www/html/static/)"
    fi
fi

echo "=== Setup Complete ==="
echo "If the site is offline (502), Nginx will now serve /static/maintenance.html"
