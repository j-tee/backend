#!/bin/bash
# Quick Server Setup Script
# Run this on the server: bash setup_production.sh

set -e  # Exit on error

echo "========================================="
echo "POS Backend Production Setup"
echo "========================================="
echo ""

# Check if .env.production already exists
if [ -f "/var/www/pos/backend/.env.production" ]; then
    echo "⚠️  .env.production already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping .env.production creation..."
    else
        rm /var/www/pos/backend/.env.production
    fi
fi

# Prompt for database credentials
echo "Enter your PostgreSQL database credentials:"
echo "(Press Enter to use default values shown in brackets)"
echo ""

read -p "Database name [pos_db]: " db_name
db_name=${db_name:-pos_db}

read -p "Database user [postgres]: " db_user
db_user=${db_user:-postgres}

read -sp "Database password: " db_password
echo ""

read -p "Database host [localhost]: " db_host
db_host=${db_host:-localhost}

read -p "Database port [5432]: " db_port
db_port=${db_port:-5432}

echo ""
read -p "Server domain or IP [68.66.251.79]: " server_host
server_host=${server_host:-68.66.251.79}

echo ""
echo "Generating SECRET_KEY..."
secret_key=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

# Create .env.production file
echo ""
echo "Creating .env.production file..."
cat > /var/www/pos/backend/.env.production << EOF
# Production Environment Variables
# Auto-generated on $(date)

# Django Settings
SECRET_KEY=${secret_key}
DEBUG=False
ALLOWED_HOSTS=${server_host},localhost,127.0.0.1

# Database Settings
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
DB_HOST=${db_host}
DB_PORT=${db_port}

# Redis Settings
REDIS_URL=redis://localhost:6379/0
USE_REDIS_CACHE=True

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Email Settings (Update these if you want email functionality)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Platform Settings
PLATFORM_OWNER_EMAIL=juliustetteh@gmail.com

# Payment Gateway Settings
PAYMENT_GATEWAY_MODE=test
PAYSTACK_SECRET_KEY=
STRIPE_SECRET_KEY=

# Security Settings (Enable these when you have SSL)
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True

# Extra
ENV_NAME=production
EOF

echo "✅ .env.production created!"

# Secure the file
chmod 600 /var/www/pos/backend/.env.production
echo "✅ File permissions set to 600"

# Create required directories
echo ""
echo "Creating required directories..."
mkdir -p /var/www/pos/backend/logs
mkdir -p /var/www/pos/backend/staticfiles
mkdir -p /var/www/pos/backend/media
echo "✅ Directories created"

# Test database connection
echo ""
echo "Testing database connection..."
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=/var/www/pos/backend/.env.production

if python manage.py check --database default 2>/dev/null; then
    echo "✅ Database connection successful!"
else
    echo "❌ Database connection failed!"
    echo "Please check your database credentials and ensure PostgreSQL is running."
    exit 1
fi

# Install systemd services
echo ""
echo "Installing systemd services..."
if sudo cp /var/www/pos/backend/deployment/*.service /etc/systemd/system/ 2>/dev/null; then
    sudo systemctl daemon-reload
    echo "✅ Services installed"
    
    # Enable services
    echo "Enabling services..."
    sudo systemctl enable gunicorn celery celery-beat
    echo "✅ Services enabled"
else
    echo "⚠️  Could not install services (requires sudo). Please run manually:"
    echo "    sudo cp /var/www/pos/backend/deployment/*.service /etc/systemd/system/"
    echo "    sudo systemctl daemon-reload"
    echo "    sudo systemctl enable gunicorn celery celery-beat"
fi

# Run migrations
echo ""
echo "Running database migrations..."
python manage.py migrate
echo "✅ Migrations completed"

# Collect static files
echo ""
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✅ Static files collected"

# Start services
echo ""
echo "Starting services..."
if sudo systemctl start gunicorn celery celery-beat 2>/dev/null; then
    echo "✅ Services started"
else
    echo "⚠️  Could not start services (requires sudo). Please run manually:"
    echo "    sudo systemctl start gunicorn celery celery-beat"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Create a superuser: python manage.py createsuperuser"
echo "2. Configure passwordless sudo for deploy user (see SERVER_SETUP_GUIDE.md)"
echo "3. Test the deployment from GitHub Actions"
echo ""
echo "To check service status:"
echo "    sudo systemctl status gunicorn"
echo "    sudo systemctl status celery"
echo "    sudo systemctl status celery-beat"
echo ""
