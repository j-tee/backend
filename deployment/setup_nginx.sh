#!/bin/bash
# Setup Nginx Server Block for POS Backend
# Run this script on the production server

set -e

echo "=== POS Backend Nginx Setup ==="
echo ""

# Configuration
NGINX_CONF_DIR="/opt/nginx/conf/conf.d"
SOURCE_CONF="/var/www/pos/backend/deployment/pos_backend.conf"
DEST_CONF="$NGINX_CONF_DIR/pos_backend.conf"

# Step 1: Check if nginx config directory exists
if [ ! -d "$NGINX_CONF_DIR" ]; then
    echo "❌ Error: Nginx config directory not found at $NGINX_CONF_DIR"
    exit 1
fi

echo "✅ Nginx config directory found"

# Step 2: Backup existing config if it exists
if [ -f "$DEST_CONF" ]; then
    echo "⚠️  Existing config found. Creating backup..."
    sudo cp "$DEST_CONF" "$DEST_CONF.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Backup created"
fi

# Step 3: Copy the new configuration
echo "📋 Copying new nginx configuration..."
sudo cp "$SOURCE_CONF" "$DEST_CONF"
echo "✅ Configuration copied"

# Step 4: Update domain name (interactive)
echo ""
read -p "Enter your domain name (or press Enter to skip): " DOMAIN_NAME

if [ ! -z "$DOMAIN_NAME" ]; then
    echo "🔧 Updating domain name to: $DOMAIN_NAME"
    sudo sed -i "s/pos-api.yourdomain.com/$DOMAIN_NAME/g" "$DEST_CONF"
    echo "✅ Domain name updated"
else
    echo "⚠️  Skipped domain name update. Edit $DEST_CONF manually later."
fi

# Step 5: Test nginx configuration
echo ""
echo "🧪 Testing nginx configuration..."
if sudo /opt/nginx/sbin/nginx -t; then
    echo "✅ Nginx configuration is valid"
else
    echo "❌ Nginx configuration test failed!"
    echo "Please check the configuration file: $DEST_CONF"
    exit 1
fi

# Step 6: Reload nginx
echo ""
read -p "Reload nginx now? (y/n): " RELOAD_CHOICE

if [ "$RELOAD_CHOICE" = "y" ] || [ "$RELOAD_CHOICE" = "Y" ]; then
    echo "🔄 Reloading nginx..."
    if sudo /opt/nginx/sbin/nginx -s reload; then
        echo "✅ Nginx reloaded successfully"
    else
        echo "❌ Failed to reload nginx"
        exit 1
    fi
else
    echo "⚠️  Skipped nginx reload. Remember to reload manually:"
    echo "   sudo /opt/nginx/sbin/nginx -s reload"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "📝 Next steps:"
echo "1. Update DNS records to point to this server"
echo "2. Ensure gunicorn service is running:"
echo "   sudo systemctl status gunicorn"
echo "3. Check logs if needed:"
echo "   tail -f /var/www/pos/backend/logs/nginx_access.log"
echo "   tail -f /var/www/pos/backend/logs/nginx_error.log"
echo ""
echo "🔒 For SSL/HTTPS setup:"
echo "   Install certbot and run: sudo certbot --nginx -d $DOMAIN_NAME"
echo ""
