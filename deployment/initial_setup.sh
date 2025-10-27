#!/bin/bash

# POS Backend Initial Server Setup Script
# Run this script on your VPS as the deploy user

set -e  # Exit on error

echo "========================================="
echo "POS Backend - Initial Server Setup"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as deploy user
if [ "$USER" != "deploy" ]; then
    echo -e "${RED}Error: This script should be run as the 'deploy' user${NC}"
    echo "Switch to deploy user: su - deploy"
    exit 1
fi

# Variables
PROJECT_DIR="/var/www/pos/backend"
REPO_URL="git@github.com:YOUR_USERNAME/YOUR_REPO.git"  # Update this with your repo
BRANCH="main"

echo -e "${YELLOW}Step 1: Installing system dependencies...${NC}"
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib \
    redis-server nginx git supervisor curl build-essential libpq-dev python3-dev

echo -e "${GREEN}✓ System dependencies installed${NC}"

echo -e "${YELLOW}Step 2: Setting up PostgreSQL database...${NC}"
sudo -u postgres psql << EOF
CREATE DATABASE pos_production;
CREATE USER pos_user WITH PASSWORD 'CHANGE_THIS_PASSWORD';
ALTER ROLE pos_user SET client_encoding TO 'utf8';
ALTER ROLE pos_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE pos_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE pos_production TO pos_user;
\q
EOF

echo -e "${GREEN}✓ PostgreSQL database created${NC}"

echo -e "${YELLOW}Step 3: Setting up project directory...${NC}"
cd /var/www/pos/backend

# Create necessary directories
mkdir -p logs media staticfiles

echo -e "${YELLOW}Step 4: Creating Python virtual environment...${NC}"
python3.11 -m venv venv
source venv/bin/activate

echo -e "${GREEN}✓ Virtual environment created${NC}"

echo -e "${YELLOW}Step 5: Cloning repository...${NC}"
# If directory is empty, clone; otherwise pull
if [ -z "$(ls -A $PROJECT_DIR)" ]; then
    git clone -b $BRANCH $REPO_URL .
else
    git pull origin $BRANCH
fi

echo -e "${GREEN}✓ Repository cloned${NC}"

echo -e "${YELLOW}Step 6: Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo -e "${YELLOW}Step 7: Setting up environment file...${NC}"
if [ ! -f .env.production ]; then
    cp .env.production.example .env.production
    echo -e "${YELLOW}⚠ Please edit .env.production with your actual configuration${NC}"
    echo -e "${YELLOW}  nano .env.production${NC}"
else
    echo -e "${GREEN}✓ .env.production already exists${NC}"
fi

echo -e "${YELLOW}Step 8: Running Django migrations...${NC}"
export DJANGO_ENV_FILE=.env.production
python manage.py migrate

echo -e "${GREEN}✓ Migrations completed${NC}"

echo -e "${YELLOW}Step 9: Collecting static files...${NC}"
python manage.py collectstatic --noinput

echo -e "${GREEN}✓ Static files collected${NC}"

echo -e "${YELLOW}Step 10: Creating superuser (optional)...${NC}"
read -p "Do you want to create a Django superuser now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi

echo -e "${YELLOW}Step 11: Setting up systemd services...${NC}"
sudo cp deployment/gunicorn.service /etc/systemd/system/posbackend.service
sudo cp deployment/celery.service /etc/systemd/system/posbackend-celery.service
sudo cp deployment/celery-beat.service /etc/systemd/system/posbackend-celery-beat.service

sudo systemctl daemon-reload
sudo systemctl enable posbackend
sudo systemctl enable posbackend-celery
sudo systemctl enable posbackend-celery-beat

echo -e "${GREEN}✓ Systemd services configured${NC}"

echo -e "${YELLOW}Step 12: Setting up Nginx...${NC}"
sudo cp nginx.conf /etc/nginx/sites-available/posbackend
sudo ln -sf /etc/nginx/sites-available/posbackend /etc/nginx/sites-enabled/

# Test nginx configuration
if sudo nginx -t; then
    echo -e "${GREEN}✓ Nginx configuration is valid${NC}"
    
    # Reload nginx using the control script
    ./deployment/nginx_control.sh reload
else
    echo -e "${RED}✗ Nginx configuration test failed${NC}"
    echo "Please check the configuration and try again"
fi

echo -e "${GREEN}✓ Nginx configured${NC}"

echo -e "${YELLOW}Step 13: Setting correct permissions...${NC}"
sudo chown -R deploy:www-data /var/www/pos/backend
sudo chmod -R 755 /var/www/pos/backend
sudo chmod -R 775 /var/www/pos/backend/logs
sudo chmod -R 775 /var/www/pos/backend/media

echo -e "${GREEN}✓ Permissions set${NC}"

echo -e "${YELLOW}Step 14: Starting services...${NC}"
sudo systemctl start posbackend
sudo systemctl start posbackend-celery
sudo systemctl start posbackend-celery-beat

echo -e "${GREEN}✓ Services started${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}Initial setup completed!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env.production with your actual credentials"
echo "2. Update nginx.conf with your domain name"
echo "3. Set up SSL certificate using Let's Encrypt (see ssl_setup.sh)"
echo "4. Configure GitHub Actions secrets for CI/CD"
echo "5. Test your deployment: http://YOUR_SERVER_IP"
echo ""
echo "Service commands:"
echo "  sudo systemctl status posbackend"
echo "  sudo systemctl restart posbackend"
echo "  sudo systemctl logs -f posbackend"
echo ""
echo "View logs:"
echo "  tail -f logs/gunicorn_error.log"
echo "  tail -f logs/celery_worker.log"
echo ""
