#!/bin/bash

# Health Check Script
# Run this to verify all services are working correctly

set -e

echo "========================================="
echo "POS Backend - Health Check"
echo "========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_service() {
    if systemctl is-active --quiet $1; then
        echo -e "${GREEN}✓${NC} $1 is running"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is NOT running"
        return 1
    fi
}

check_port() {
    if netstat -tuln | grep -q ":$1 "; then
        echo -e "${GREEN}✓${NC} Port $1 is listening"
        return 0
    else
        echo -e "${RED}✗${NC} Port $1 is NOT listening"
        return 1
    fi
}

echo ""
echo "Checking System Services..."
echo "----------------------------"

check_service postgresql
check_service redis

# Check Nginx (handle different installation methods)
if systemctl list-unit-files 2>/dev/null | grep -q nginx.service; then
    check_service nginx
elif pgrep nginx >/dev/null; then
    echo -e "${GREEN}✓${NC} nginx is running (source-compiled)"
else
    echo -e "${RED}✗${NC} nginx is NOT running"
fi

check_service posbackend
check_service posbackend-celery
check_service posbackend-celery-beat

echo ""
echo "Checking Network Ports..."
echo "-------------------------"

check_port 5432  # PostgreSQL
check_port 6379  # Redis
check_port 80    # Nginx HTTP
# check_port 443   # Nginx HTTPS (uncomment after SSL setup)

echo ""
echo "Checking Application Files..."
echo "-----------------------------"

PROJECT_DIR="/var/www/pos/backend"

if [ -f "$PROJECT_DIR/gunicorn.sock" ]; then
    echo -e "${GREEN}✓${NC} Gunicorn socket exists"
else
    echo -e "${RED}✗${NC} Gunicorn socket missing"
fi

if [ -d "$PROJECT_DIR/staticfiles" ] && [ "$(ls -A $PROJECT_DIR/staticfiles)" ]; then
    echo -e "${GREEN}✓${NC} Static files collected"
else
    echo -e "${YELLOW}⚠${NC} Static files may not be collected"
fi

if [ -f "$PROJECT_DIR/.env.production" ]; then
    echo -e "${GREEN}✓${NC} Production environment file exists"
else
    echo -e "${RED}✗${NC} Production environment file missing"
fi

echo ""
echo "Checking Disk Space..."
echo "----------------------"

df -h / | tail -n 1 | awk '{print "Used: "$3" / "$2" ("$5")"}'

USAGE=$(df / | tail -n 1 | awk '{print $5}' | sed 's/%//')
if [ $USAGE -gt 80 ]; then
    echo -e "${RED}⚠ Warning: Disk usage is above 80%${NC}"
fi

echo ""
echo "Recent Errors in Logs..."
echo "------------------------"

if [ -f "$PROJECT_DIR/logs/gunicorn_error.log" ]; then
    ERROR_COUNT=$(grep -i "error" "$PROJECT_DIR/logs/gunicorn_error.log" | tail -n 5 | wc -l)
    if [ $ERROR_COUNT -gt 0 ]; then
        echo -e "${YELLOW}Found $ERROR_COUNT recent errors in Gunicorn logs${NC}"
        echo "Last 3 errors:"
        grep -i "error" "$PROJECT_DIR/logs/gunicorn_error.log" | tail -n 3
    else
        echo -e "${GREEN}✓${NC} No recent errors in Gunicorn logs"
    fi
fi

echo ""
echo "Testing Application Response..."
echo "--------------------------------"

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")

if [ "$RESPONSE" == "200" ] || [ "$RESPONSE" == "301" ] || [ "$RESPONSE" == "302" ]; then
    echo -e "${GREEN}✓${NC} Application responding (HTTP $RESPONSE)"
else
    echo -e "${RED}✗${NC} Application not responding correctly (HTTP $RESPONSE)"
fi

echo ""
echo "Database Connection..."
echo "----------------------"

cd $PROJECT_DIR
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production

if python manage.py check --deploy > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Django deployment check passed"
else
    echo -e "${RED}✗${NC} Django deployment check failed"
    echo "Run: python manage.py check --deploy"
fi

echo ""
echo "========================================="
echo "Health check completed!"
echo "========================================="
echo ""
