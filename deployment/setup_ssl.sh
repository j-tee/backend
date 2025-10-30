#!/bin/bash
# Setup SSL Certificate for POS Backend using Certbot
# Run this script on the production server AFTER nginx is configured

set -e

echo "=== SSL Certificate Setup for POS Backend ==="
echo ""

# Configuration
DOMAIN="posbackend.alphalogiquetechnologies.com"
EMAIL="juliustetteh@gmail.com"  # Change this to your email
NGINX_SBIN="/opt/nginx/sbin/nginx"
NGINX_CONF="/opt/nginx/conf/conf.d/pos_backend.conf"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if certbot is installed
echo "🔍 Checking for certbot..."
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}⚠️  Certbot not found. Installing...${NC}"
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
    echo -e "${GREEN}✅ Certbot installed${NC}"
else
    echo -e "${GREEN}✅ Certbot is already installed${NC}"
fi

# Step 2: Verify domain is accessible
echo ""
echo "🌐 Verifying domain is accessible..."
if curl -f -s -o /dev/null "http://$DOMAIN"; then
    echo -e "${GREEN}✅ Domain $DOMAIN is accessible${NC}"
else
    echo -e "${RED}❌ Warning: Domain $DOMAIN is not accessible yet${NC}"
    echo "   Make sure:"
    echo "   1. DNS records are properly configured"
    echo "   2. Nginx is running and serving the site"
    echo ""
    read -p "Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        echo "Exiting..."
        exit 1
    fi
fi

# Step 3: Update email if needed
echo ""
read -p "Email for SSL notifications (default: $EMAIL): " USER_EMAIL
if [ ! -z "$USER_EMAIL" ]; then
    EMAIL="$USER_EMAIL"
fi

# Step 4: Run certbot
echo ""
echo "🔒 Obtaining SSL certificate for $DOMAIN..."
echo "   Email: $EMAIL"
echo ""

# Use certbot with manual nginx configuration
if sudo certbot certonly --webroot \
    -w /var/www/pos/backend/staticfiles \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive; then
    
    echo -e "${GREEN}✅ SSL certificate obtained successfully!${NC}"
else
    echo -e "${RED}❌ Failed to obtain SSL certificate${NC}"
    echo ""
    echo "Trying alternative method (standalone)..."
    echo "This will temporarily stop nginx..."
    
    sudo systemctl stop nginx || sudo $NGINX_SBIN -s stop
    
    if sudo certbot certonly --standalone \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive; then
        
        echo -e "${GREEN}✅ SSL certificate obtained successfully!${NC}"
        sudo systemctl start nginx || sudo $NGINX_SBIN
    else
        echo -e "${RED}❌ Failed to obtain SSL certificate${NC}"
        sudo systemctl start nginx || sudo $NGINX_SBIN
        exit 1
    fi
fi

# Step 5: Update nginx configuration for SSL
echo ""
echo "📝 Updating nginx configuration for SSL..."

# Backup current config
sudo cp "$NGINX_CONF" "$NGINX_CONF.backup.$(date +%Y%m%d_%H%M%S)"

# Create SSL-enabled config
sudo tee "$NGINX_CONF" > /dev/null <<'EOF'
# POS Backend API Server Block with SSL
# Managed by deployment/setup_ssl.sh

upstream pos_backend {
    server unix:/var/www/pos/backend/gunicorn.sock fail_timeout=0;
}

# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    
    server_name posbackend.alphalogiquetechnologies.com;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name posbackend.alphalogiquetechnologies.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/privkey.pem;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/chain.pem;
    
    charset utf-8;
    client_max_body_size 75M;
    
    # Access and error logs
    access_log /var/www/pos/backend/logs/nginx_access.log;
    error_log /var/www/pos/backend/logs/nginx_error.log;
    
    # Static files
    location /static/ {
        alias /var/www/pos/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /var/www/pos/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Main application
    location / {
        proxy_pass http://pos_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Disable access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

echo -e "${GREEN}✅ Nginx configuration updated${NC}"

# Step 6: Test nginx configuration
echo ""
echo "🧪 Testing nginx configuration..."
if sudo $NGINX_SBIN -t; then
    echo -e "${GREEN}✅ Nginx configuration is valid${NC}"
else
    echo -e "${RED}❌ Nginx configuration test failed!${NC}"
    echo "Restoring backup..."
    sudo cp "$NGINX_CONF.backup.$(date +%Y%m%d_%H%M%S)" "$NGINX_CONF"
    exit 1
fi

# Step 7: Reload nginx
echo ""
echo "🔄 Reloading nginx..."
if sudo $NGINX_SBIN -s reload; then
    echo -e "${GREEN}✅ Nginx reloaded successfully${NC}"
else
    echo -e "${RED}❌ Failed to reload nginx${NC}"
    exit 1
fi

# Step 8: Setup auto-renewal
echo ""
echo "⏰ Setting up automatic certificate renewal..."

# Test renewal
if sudo certbot renew --dry-run; then
    echo -e "${GREEN}✅ Certificate auto-renewal is configured${NC}"
    echo "   Certificates will auto-renew before expiration"
else
    echo -e "${YELLOW}⚠️  Auto-renewal test had issues${NC}"
fi

# Step 9: Update Django settings reminder
echo ""
echo -e "${GREEN}=== SSL Setup Complete! ===${NC}"
echo ""
echo "📋 Important: Update Django settings"
echo "   Add to .env.production:"
echo "   SECURE_SSL_REDIRECT=True"
echo "   SESSION_COOKIE_SECURE=True"
echo "   CSRF_COOKIE_SECURE=True"
echo "   SECURE_HSTS_SECONDS=31536000"
echo ""
echo "🔗 Your site is now available at:"
echo "   https://posbackend.alphalogiquetechnologies.com"
echo ""
echo "🔒 SSL Certificate Information:"
sudo certbot certificates -d "$DOMAIN"
echo ""
echo "📅 Auto-renewal: Certificates will auto-renew via systemd timer"
echo "   Check status: sudo systemctl status certbot.timer"
echo ""
