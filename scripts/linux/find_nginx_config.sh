#!/bin/bash
# Script to find Nginx configuration files on the VPS
# Run this on the server: ./find_nginx_config.sh

echo "=== Nginx Configuration Locator ==="

# 1. Check if Nginx is installed/running
if ! command -v nginx >/dev/null 2>&1; then
    echo "Error: Nginx is not installed or not in PATH."
    exit 1
fi

# 2. Find Main Config File
echo "--- Main Configuration ---"
MAIN_CONF=$(nginx -t 2>&1 | grep "configuration file" | awk '{print $5}')
if [ -z "$MAIN_CONF" ]; then
    echo "Could not determine main config file."
    # Fallback attempt
    if [ -f "/etc/nginx/nginx.conf" ]; then
        MAIN_CONF="/etc/nginx/nginx.conf"
        echo "Assuming default: $MAIN_CONF"
    fi
else
    echo "Main Config File: $MAIN_CONF"
fi

# 3. Find Site Configurations (Server Blocks)
echo ""
echo "--- Site Configurations ---"
echo "Searching for 'votebem' or 'server_name' in common directories..."

CONF_DIRS=("/etc/nginx/sites-enabled" "/etc/nginx/conf.d" "/etc/nginx/sites-available")
FOUND=0

for DIR in "${CONF_DIRS[@]}"; do
    if [ -d "$DIR" ]; then
        echo "Checking $DIR..."
        # Grep for votebem.online or general server blocks
        MATCHES=$(grep -l "votebem.online" "$DIR"/* 2>/dev/null)
        
        if [ -n "$MATCHES" ]; then
            echo "  Found 'votebem.online' in:"
            for FILE in $MATCHES; do
                echo "    -> $FILE  <-- (Likely the one you want!)"
                FOUND=1
            done
        else
            # If specific domain not found, list active files
            echo "  No explicit 'votebem.online' match. Listing active files:"
            ls -1 "$DIR"/*.conf 2>/dev/null | sed 's/^/    - /'
            ls -1 "$DIR"/* 2>/dev/null | grep -v "\.conf$" | sed 's/^/    - /' # for sites-enabled links
        fi
    fi
done

if [ $FOUND -eq 0 ]; then
    echo ""
    echo "Could not find a specific config file containing 'votebem.online'."
    echo "You may be using the default config or a generic include."
    echo "Try: grep -r 'server_name' /etc/nginx/"
fi

echo ""
echo "--- Next Steps ---"
echo "1. Edit the file identified above (e.g., sudo nano /etc/nginx/sites-enabled/votebem)"
echo "2. Add the maintenance config:"
echo "   error_page 502 503 504 /static/maintenance.html;"
echo "   location /static/ { ... }"
echo "3. Test config: sudo nginx -t"
echo "4. Restart: sudo systemctl restart nginx"
