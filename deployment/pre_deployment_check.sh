#!/bin/bash

# Pre-deployment Checklist Script
# Run this before deploying to production

echo "========================================="
echo "Pre-Deployment Checklist"
echo "========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

echo ""
echo "Checking Configuration Files..."
echo "--------------------------------"

# Check .env.production.example exists
if [ -f ".env.production.example" ]; then
    check_pass ".env.production.example exists"
else
    check_fail ".env.production.example is missing"
fi

# Check GitHub workflow exists
if [ -f ".github/workflows/deploy.yml" ]; then
    check_pass "GitHub Actions workflow configured"
else
    check_fail "GitHub Actions workflow missing"
fi

# Check deployment scripts exist
if [ -d "deployment" ]; then
    check_pass "Deployment directory exists"
    
    for script in initial_setup.sh deploy.sh ssl_setup.sh health_check.sh; do
        if [ -f "deployment/$script" ]; then
            check_pass "deployment/$script exists"
        else
            check_warn "deployment/$script is missing"
        fi
    done
else
    check_fail "Deployment directory missing"
fi

# Check nginx config
if [ -f "nginx.conf" ]; then
    check_pass "Nginx configuration exists"
else
    check_fail "nginx.conf is missing"
fi

echo ""
echo "Checking Django Settings..."
echo "---------------------------"

# Check if DEBUG is False in production
if grep -q "DEBUG = config('DEBUG', cast=bool, default=False)" app/settings.py; then
    check_pass "DEBUG defaults to False"
else
    check_warn "DEBUG setting may not be properly configured"
fi

# Check SECRET_KEY configuration
if grep -q "SECRET_KEY = config('SECRET_KEY'" app/settings.py; then
    check_pass "SECRET_KEY uses environment variable"
else
    check_fail "SECRET_KEY is hardcoded (security risk!)"
fi

# Check ALLOWED_HOSTS configuration
if grep -q "ALLOWED_HOSTS = " app/settings.py; then
    check_pass "ALLOWED_HOSTS is configured"
else
    check_warn "ALLOWED_HOSTS may not be configured"
fi

# Check database configuration
if grep -q "DATABASES = {" app/settings.py; then
    check_pass "Database configuration found"
else
    check_fail "Database configuration missing"
fi

echo ""
echo "Checking Dependencies..."
echo "------------------------"

# Check requirements.txt
if [ -f "requirements.txt" ]; then
    check_pass "requirements.txt exists"
    
    # Check for essential packages
    for pkg in Django djangorestframework gunicorn psycopg celery redis; do
        if grep -qi "$pkg" requirements.txt; then
            check_pass "$pkg is in requirements.txt"
        else
            check_warn "$pkg may be missing from requirements.txt"
        fi
    done
else
    check_fail "requirements.txt is missing"
fi

echo ""
echo "Checking Security..."
echo "--------------------"

# Check if .env files are gitignored
if grep -q "*.env" .gitignore; then
    check_pass ".env files are in .gitignore"
else
    check_fail ".env files are NOT in .gitignore (security risk!)"
fi

# Check if db.sqlite3 is gitignored
if grep -q "db.sqlite3" .gitignore; then
    check_pass "SQLite database is gitignored"
else
    check_warn "SQLite database may not be gitignored"
fi

# Check if logs are gitignored
if grep -q "logs/" .gitignore; then
    check_pass "Logs directory is gitignored"
else
    check_warn "Logs directory may not be gitignored"
fi

echo ""
echo "Checking Git Status..."
echo "----------------------"

# Check if git repo is initialized
if [ -d ".git" ]; then
    check_pass "Git repository initialized"
    
    # Check for uncommitted changes
    if [ -z "$(git status --porcelain)" ]; then
        check_pass "No uncommitted changes"
    else
        check_warn "There are uncommitted changes"
        git status --short
    fi
    
    # Check current branch
    BRANCH=$(git branch --show-current)
    echo "Current branch: $BRANCH"
    
else
    check_fail "Git repository not initialized"
fi

echo ""
echo "Checking Test Coverage..."
echo "-------------------------"

# Check if tests exist
TEST_FILES=$(find . -name "test*.py" -o -name "*test.py" | wc -l)
if [ $TEST_FILES -gt 0 ]; then
    check_pass "Found $TEST_FILES test files"
else
    check_warn "No test files found"
fi

echo ""
echo "========================================="
echo "Summary"
echo "========================================="
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${YELLOW}Warnings: $WARN${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}⚠ Please fix the failed items before deploying!${NC}"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo -e "${YELLOW}⚠ Review warnings before deploying${NC}"
    exit 0
else
    echo -e "${GREEN}✓ All checks passed! Ready to deploy.${NC}"
    exit 0
fi
