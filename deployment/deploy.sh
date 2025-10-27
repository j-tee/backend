#!/bin/bash

# Manual Deployment Script
# Use this for manual deployments when not using CI/CD

set -e

echo "========================================="
echo "POS Backend - Manual Deployment"
echo "========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/var/www/pos/backend"

cd $PROJECT_DIR

echo -e "${YELLOW}Step 1: Pulling latest code...${NC}"
git pull origin main

echo -e "${GREEN}✓ Code updated${NC}"

echo -e "${YELLOW}Step 2: Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${YELLOW}Step 3: Installing/updating dependencies...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}✓ Dependencies updated${NC}"

echo -e "${YELLOW}Step 4: Running migrations...${NC}"
export DJANGO_ENV_FILE=.env.production
python manage.py migrate --noinput

echo -e "${GREEN}✓ Migrations completed${NC}"

echo -e "${YELLOW}Step 5: Collecting static files...${NC}"
python manage.py collectstatic --noinput

echo -e "${GREEN}✓ Static files collected${NC}"

echo -e "${YELLOW}Step 6: Restarting services...${NC}"
sudo systemctl restart posbackend
sudo systemctl restart posbackend-celery
sudo systemctl restart posbackend-celery-beat

# Use the nginx control script for flexible nginx management
./deployment/nginx_control.sh reload

echo -e "${GREEN}✓ Services restarted${NC}"

echo -e "${YELLOW}Step 7: Checking service status...${NC}"
sleep 3
sudo systemctl status posbackend --no-pager

echo ""
echo "========================================="
echo -e "${GREEN}Deployment completed!${NC}"
echo "========================================="
echo ""
echo "Check logs if there are any issues:"
echo "  tail -f logs/gunicorn_error.log"
echo "  sudo journalctl -u posbackend -f"
echo ""
