#!/bin/bash

# SSL Setup Script using Let's Encrypt
# Run this after your domain is pointing to your server

set -e

echo "========================================="
echo "Setting up SSL with Let's Encrypt"
echo "========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Installing Certbot...${NC}"
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

echo -e "${YELLOW}Please enter your domain name (e.g., api.yourdomain.com):${NC}"
read DOMAIN

echo -e "${YELLOW}Please enter your email address:${NC}"
read EMAIL

echo -e "${YELLOW}Obtaining SSL certificate...${NC}"
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --no-eff-email

echo -e "${GREEN}✓ SSL certificate obtained${NC}"

echo -e "${YELLOW}Setting up auto-renewal...${NC}"
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo -e "${GREEN}✓ Auto-renewal configured${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}SSL setup completed!${NC}"
echo "========================================="
echo ""
echo "Your site should now be accessible via HTTPS"
echo "Certificate will auto-renew before expiration"
echo ""
echo "To test renewal: sudo certbot renew --dry-run"
echo ""
