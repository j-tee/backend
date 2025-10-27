#!/bin/bash

# Server Readiness Assessment Script
# Run this on your VPS to check deployment preparedness

echo "========================================="
echo "POS Backend - Server Readiness Check"
echo "========================================="
echo ""
echo "Server: $(hostname)"
echo "User: $(whoami)"
echo "Date: $(date)"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# ============================================
# SYSTEM INFORMATION
# ============================================
echo "========================================="
echo "1. SYSTEM INFORMATION"
echo "========================================="

# OS Version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    check_info "OS: $PRETTY_NAME"
else
    check_warn "Cannot determine OS version"
fi

# Kernel
check_info "Kernel: $(uname -r)"

# Architecture
check_info "Architecture: $(uname -m)"

# Memory
TOTAL_MEM=$(free -h | grep Mem | awk '{print $2}')
USED_MEM=$(free -h | grep Mem | awk '{print $3}')
check_info "Memory: $USED_MEM used of $TOTAL_MEM"

# Disk Space
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
DISK_AVAIL=$(df -h / | tail -1 | awk '{print $4}')
if [ $DISK_USAGE -lt 80 ]; then
    check_pass "Disk space: ${DISK_AVAIL} available (${DISK_USAGE}% used)"
else
    check_warn "Disk space: Only ${DISK_AVAIL} available (${DISK_USAGE}% used)"
fi

echo ""

# ============================================
# PYTHON ENVIRONMENT
# ============================================
echo "========================================="
echo "2. PYTHON ENVIRONMENT"
echo "========================================="

# Python 3.11
if command -v python3.11 &> /dev/null; then
    PYTHON_VERSION=$(python3.11 --version)
    check_pass "Python 3.11: $PYTHON_VERSION"
else
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        check_warn "Python 3.11 not found, but found: $PYTHON_VERSION"
    else
        check_fail "Python 3 not installed"
    fi
fi

# pip
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version)
    check_pass "pip3: $PIP_VERSION"
else
    check_fail "pip3 not installed"
fi

# python3-venv
if dpkg -l | grep -q python3-venv; then
    check_pass "python3-venv package installed"
else
    check_warn "python3-venv package not installed"
fi

# Check for virtual environment tools
if command -v virtualenv &> /dev/null; then
    check_info "virtualenv available"
fi

echo ""

# ============================================
# DATABASE - PostgreSQL
# ============================================
echo "========================================="
echo "3. POSTGRESQL DATABASE"
echo "========================================="

if command -v psql &> /dev/null; then
    PG_VERSION=$(psql --version)
    check_pass "PostgreSQL: $PG_VERSION"
    
    # Check if PostgreSQL is running
    if systemctl is-active --quiet postgresql; then
        check_pass "PostgreSQL service is running"
    else
        check_fail "PostgreSQL service is not running"
    fi
    
    # Check PostgreSQL port
    if netstat -tuln 2>/dev/null | grep -q ":5432"; then
        check_pass "PostgreSQL listening on port 5432"
    else
        check_warn "PostgreSQL not listening on port 5432"
    fi
else
    check_fail "PostgreSQL not installed"
fi

echo ""

# ============================================
# REDIS
# ============================================
echo "========================================="
echo "4. REDIS CACHE"
echo "========================================="

if command -v redis-server &> /dev/null; then
    REDIS_VERSION=$(redis-server --version | cut -d' ' -f3)
    check_pass "Redis: $REDIS_VERSION"
    
    # Check if Redis is running
    if systemctl is-active --quiet redis 2>/dev/null || systemctl is-active --quiet redis-server 2>/dev/null; then
        check_pass "Redis service is running"
    else
        check_warn "Redis service not running"
    fi
    
    # Test Redis connection
    if redis-cli ping 2>/dev/null | grep -q PONG; then
        check_pass "Redis responding to ping"
    else
        check_warn "Redis not responding"
    fi
else
    check_fail "Redis not installed"
fi

echo ""

# ============================================
# NGINX WEB SERVER
# ============================================
echo "========================================="
echo "5. NGINX WEB SERVER"
echo "========================================="

if command -v nginx &> /dev/null; then
    NGINX_VERSION=$(nginx -v 2>&1)
    check_pass "Nginx: $NGINX_VERSION"
    
    # Nginx binary location
    NGINX_BIN=$(which nginx)
    check_info "Nginx binary: $NGINX_BIN"
    
    # Nginx config location
    NGINX_CONF=$(nginx -t 2>&1 | grep "configuration file" | cut -d' ' -f5)
    check_info "Nginx config: $NGINX_CONF"
    
    # Check if source-compiled (custom location)
    if [[ "$NGINX_BIN" == *"/opt/nginx"* ]] || [[ "$NGINX_BIN" == *"/usr/local/nginx"* ]]; then
        check_info "Nginx is source-compiled (custom installation)"
        
        # Check for conf.d directory
        if [ -d "/opt/nginx/conf/conf.d" ]; then
            check_pass "Found conf.d directory: /opt/nginx/conf/conf.d"
            CONF_COUNT=$(ls -1 /opt/nginx/conf/conf.d/*.conf 2>/dev/null | wc -l)
            check_info "Existing server blocks: $CONF_COUNT"
        fi
    else
        check_info "Nginx is package-installed"
    fi
    
    # Check if Nginx is running
    if pgrep nginx >/dev/null; then
        check_pass "Nginx is running"
    else
        check_warn "Nginx is not running"
    fi
    
    # Check Nginx management method
    if systemctl list-unit-files 2>/dev/null | grep -q nginx.service; then
        check_pass "Nginx managed by systemd"
    elif [ -f /etc/init.d/nginx ]; then
        check_info "Nginx managed by init.d"
    else
        check_warn "Nginx not managed by systemd (will use signals)"
    fi
    
    # Test Nginx config
    if nginx -t 2>&1 | grep -q "syntax is ok"; then
        check_pass "Nginx configuration is valid"
    else
        check_warn "Nginx configuration has errors"
    fi
else
    check_fail "Nginx not installed"
fi

echo ""

# ============================================
# PYTHON PACKAGES
# ============================================
echo "========================================="
echo "6. PYTHON PACKAGES (Global)"
echo "========================================="

# Gunicorn
if pip3 show gunicorn &> /dev/null; then
    GUNICORN_VERSION=$(pip3 show gunicorn | grep Version | cut -d' ' -f2)
    check_pass "Gunicorn: $GUNICORN_VERSION (globally installed)"
else
    check_info "Gunicorn not installed globally (will be installed in venv)"
fi

# Check for other useful packages
for pkg in psycopg2-binary celery redis django; do
    if pip3 show $pkg &> /dev/null 2>&1; then
        VERSION=$(pip3 show $pkg | grep Version | cut -d' ' -f2)
        check_info "$pkg: $VERSION (globally installed)"
    fi
done

echo ""

# ============================================
# PROJECT DIRECTORY
# ============================================
echo "========================================="
echo "7. PROJECT DIRECTORY"
echo "========================================="

PROJECT_DIR="/var/www/pos/backend"

if [ -d "$PROJECT_DIR" ]; then
    check_pass "Project directory exists: $PROJECT_DIR"
    
    # Check ownership
    OWNER=$(stat -c '%U:%G' "$PROJECT_DIR" 2>/dev/null || echo "unknown")
    check_info "Owner: $OWNER"
    
    # Check if it's a git repository
    if [ -d "$PROJECT_DIR/.git" ]; then
        check_pass "Git repository initialized"
        
        # Current branch
        if command -v git &> /dev/null; then
            cd "$PROJECT_DIR"
            BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
            check_info "Current branch: $BRANCH"
        fi
    else
        check_warn "Not a git repository yet"
    fi
    
    # Check for virtual environment
    if [ -d "$PROJECT_DIR/venv" ]; then
        check_pass "Virtual environment exists"
    else
        check_warn "Virtual environment not created yet"
    fi
    
    # Check for .env files
    if [ -f "$PROJECT_DIR/.env.production" ]; then
        check_pass ".env.production file exists"
    else
        check_warn ".env.production not created yet"
    fi
    
    # Check for static files directory
    if [ -d "$PROJECT_DIR/staticfiles" ]; then
        check_info "Static files directory exists"
    fi
    
    # Check for logs directory
    if [ -d "$PROJECT_DIR/logs" ]; then
        check_pass "Logs directory exists"
    else
        check_warn "Logs directory not created yet"
    fi
else
    check_fail "Project directory does not exist: $PROJECT_DIR"
fi

echo ""

# ============================================
# GIT & SSH
# ============================================
echo "========================================="
echo "8. GIT & SSH CONFIGURATION"
echo "========================================="

# Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    check_pass "Git: $GIT_VERSION"
    
    # Git config
    GIT_USER=$(git config --global user.name 2>/dev/null || echo "not set")
    GIT_EMAIL=$(git config --global user.email 2>/dev/null || echo "not set")
    check_info "Git user: $GIT_USER <$GIT_EMAIL>"
else
    check_fail "Git not installed"
fi

# SSH keys
if [ -d ~/.ssh ]; then
    check_pass "SSH directory exists"
    
    SSH_KEY_COUNT=$(ls -1 ~/.ssh/*.pub 2>/dev/null | wc -l)
    if [ $SSH_KEY_COUNT -gt 0 ]; then
        check_pass "SSH keys found: $SSH_KEY_COUNT"
        
        # List SSH keys
        for key in ~/.ssh/*.pub; do
            if [ -f "$key" ]; then
                KEY_NAME=$(basename "$key")
                check_info "  - $KEY_NAME"
            fi
        done
    else
        check_warn "No SSH public keys found"
    fi
    
    # Check SSH config
    if [ -f ~/.ssh/config ]; then
        check_pass "SSH config file exists"
    else
        check_info "No SSH config file (optional)"
    fi
else
    check_warn "No .ssh directory found"
fi

# Test GitHub connection
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    check_pass "GitHub SSH authentication working"
else
    check_warn "GitHub SSH not configured or not working"
fi

echo ""

# ============================================
# SYSTEM DEPENDENCIES
# ============================================
echo "========================================="
echo "9. SYSTEM DEPENDENCIES"
echo "========================================="

# Build essentials
if dpkg -l | grep -q build-essential; then
    check_pass "build-essential installed"
else
    check_warn "build-essential not installed"
fi

# PostgreSQL dev files
if dpkg -l | grep -q libpq-dev; then
    check_pass "libpq-dev installed"
else
    check_warn "libpq-dev not installed (needed for psycopg)"
fi

# Python dev files
if dpkg -l | grep -q python3-dev; then
    check_pass "python3-dev installed"
else
    check_warn "python3-dev not installed"
fi

# Supervisor (optional, for process management)
if command -v supervisorctl &> /dev/null; then
    check_info "Supervisor installed (optional)"
else
    check_info "Supervisor not installed (using systemd instead)"
fi

# curl
if command -v curl &> /dev/null; then
    check_pass "curl installed"
else
    check_warn "curl not installed"
fi

# certbot (for SSL)
if command -v certbot &> /dev/null; then
    check_pass "Certbot installed (for SSL)"
else
    check_info "Certbot not installed (needed for SSL setup)"
fi

echo ""

# ============================================
# NETWORK & FIREWALL
# ============================================
echo "========================================="
echo "10. NETWORK & FIREWALL"
echo "========================================="

# Check open ports
if command -v netstat &> /dev/null || command -v ss &> /dev/null; then
    check_pass "Network tools available"
    
    # Check common ports
    for port in 80 443 5432 6379 7822; do
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            check_info "Port $port is listening"
        fi
    done
else
    check_warn "Network diagnostic tools not available"
fi

# UFW firewall
if command -v ufw &> /dev/null; then
    if ufw status 2>/dev/null | grep -q "Status: active"; then
        check_pass "UFW firewall is active"
        check_info "$(ufw status numbered 2>/dev/null | grep -E 'ALLOW|DENY' | wc -l) firewall rules configured"
    else
        check_warn "UFW firewall is installed but not active"
    fi
else
    check_info "UFW not installed (optional)"
fi

echo ""

# ============================================
# SYSTEMD SERVICES
# ============================================
echo "========================================="
echo "11. SYSTEMD SERVICES (If Deployed)"
echo "========================================="

# Check for POS Backend services
for service in posbackend posbackend-celery posbackend-celery-beat; do
    if systemctl list-unit-files 2>/dev/null | grep -q "$service.service"; then
        if systemctl is-active --quiet $service; then
            check_pass "$service service exists and is running"
        else
            check_warn "$service service exists but is not running"
        fi
    else
        check_info "$service service not installed yet (expected for first deployment)"
    fi
done

echo ""

# ============================================
# PERMISSIONS & USER
# ============================================
echo "========================================="
echo "12. PERMISSIONS & USER"
echo "========================================="

# Current user
CURRENT_USER=$(whoami)
check_info "Current user: $CURRENT_USER"

# Check if user is in www-data group
if groups | grep -q www-data; then
    check_pass "User is in www-data group"
else
    check_warn "User not in www-data group (may be added during setup)"
fi

# Check sudo access
if sudo -n true 2>/dev/null; then
    check_pass "User has passwordless sudo"
elif sudo -v 2>/dev/null; then
    check_pass "User has sudo access (with password)"
else
    check_warn "User may not have sudo access"
fi

echo ""

# ============================================
# SUMMARY
# ============================================
echo "========================================="
echo "ASSESSMENT SUMMARY"
echo "========================================="
echo ""
echo -e "${GREEN}Passed:${NC} $CHECKS_PASSED"
echo -e "${YELLOW}Warnings:${NC} $CHECKS_WARNING"
echo -e "${RED}Failed:${NC} $CHECKS_FAILED"
echo ""

# Overall readiness
TOTAL_CRITICAL=$((CHECKS_PASSED + CHECKS_FAILED))
if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Server is ready for deployment!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Clone your repository"
    echo "2. Run the initial_setup.sh script"
    echo "3. Configure .env.production"
    echo "4. Deploy your application"
elif [ $CHECKS_FAILED -le 3 ]; then
    echo -e "${YELLOW}⚠ Server is mostly ready but needs some fixes${NC}"
    echo ""
    echo "Address the failed checks above, then you should be good to go!"
else
    echo -e "${RED}✗ Server needs significant setup before deployment${NC}"
    echo ""
    echo "Please install missing dependencies and fix failed checks."
fi

echo ""
echo "========================================="
echo "Detailed recommendations in: server_assessment_$(date +%Y%m%d_%H%M%S).log"
echo "========================================="
