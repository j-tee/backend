# Production Server Setup Guide

## Prerequisites
You need to have the following information ready:
- PostgreSQL database name, user, and password
- Django SECRET_KEY (generate a secure one)
- Redis URL (if different from default)

## Step 1: SSH to Your Server
```bash
ssh deploy@68.66.251.79 -p 7822
```

## Step 2: Create .env.production File

Create the environment file with your production settings:

```bash
cat > /var/www/pos/backend/.env.production << 'EOF'
# Django Settings
SECRET_KEY=your-very-secret-key-change-this-to-something-random-and-long
DEBUG=False
ALLOWED_HOSTS=68.66.251.79,yourdomain.com

# Database Settings
DB_NAME=pos_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password_here
DB_HOST=localhost
DB_PORT=5432

# Redis Settings
REDIS_URL=redis://localhost:6379
USE_REDIS_CACHE=True

# Email Settings (optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password

# Platform Settings
PLATFORM_OWNER_EMAIL=juliustetteh@gmail.com

# Payment Keys (if using)
STRIPE_SECRET_KEY=
PAYSTACK_SECRET_KEY=
EOF
```

**⚠️ IMPORTANT: Replace the placeholder values above with your actual credentials!**

## Step 3: Secure the .env File
```bash
chmod 600 /var/www/pos/backend/.env.production
```

## Step 4: Create Required Directories
```bash
mkdir -p /var/www/pos/backend/logs
mkdir -p /var/www/pos/backend/staticfiles
mkdir -p /var/www/pos/backend/media
```

## Step 5: Install Systemd Services
```bash
sudo cp /var/www/pos/backend/deployment/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

## Step 6: Enable and Start Services
```bash
sudo systemctl enable gunicorn celery celery-beat
sudo systemctl start gunicorn celery celery-beat
```

## Step 7: Check Service Status
```bash
sudo systemctl status gunicorn
sudo systemctl status celery
sudo systemctl status celery-beat
```

## Step 8: Configure Passwordless Sudo (for automated deployments)

Edit the sudoers file:
```bash
sudo visudo
```

Add these lines at the end (replace `deploy` if your username is different):
```
# Allow deploy user to restart services and reload nginx without password
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery-beat
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status gunicorn
deploy ALL=(ALL) NOPASSWD: /opt/nginx/sbin/nginx -t
deploy ALL=(ALL) NOPASSWD: /opt/nginx/sbin/nginx -s reload
```

Save and exit (Ctrl+X, then Y, then Enter in nano; or :wq in vim)

## Step 9: Test Database Connection
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=/var/www/pos/backend/.env.production
python manage.py check --database default
```

If successful, you should see "System check identified no issues"

## Step 10: Run Migrations
```bash
python manage.py migrate
```

## Step 11: Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

## Step 12: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

## Step 13: Restart All Services
```bash
sudo systemctl restart gunicorn celery celery-beat
sudo /opt/nginx/sbin/nginx -t && sudo /opt/nginx/sbin/nginx -s reload
```

## Step 14: Verify Everything is Running
```bash
# Check services
sudo systemctl status gunicorn celery celery-beat

# Check if gunicorn socket exists
ls -l /var/www/pos/backend/gunicorn.sock

# Check logs if there are issues
tail -f /var/www/pos/backend/logs/gunicorn_error.log
tail -f /var/www/pos/backend/logs/celery_worker.log
```

## Troubleshooting

### If gunicorn fails to start:
```bash
# Check the logs
sudo journalctl -u gunicorn -n 50

# Or check the error log
tail -f /var/www/pos/backend/logs/gunicorn_error.log
```

### If database connection fails:
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check database credentials in `.env.production`
- Test connection: `psql -U postgres -d pos_db -h localhost`

### If celery fails:
```bash
# Check celery logs
tail -f /var/www/pos/backend/logs/celery_worker.log

# Check if Redis is running
redis-cli ping
```

## After Setup is Complete

Once all these steps are done:
1. Push any changes to your `main` branch
2. GitHub Actions will automatically deploy
3. The deployment will pull latest code, run migrations, collect static files, and restart services

## Quick Reference Commands

```bash
# Restart all services
sudo systemctl restart gunicorn celery celery-beat

# View logs
tail -f /var/www/pos/backend/logs/gunicorn_error.log
tail -f /var/www/pos/backend/logs/celery_worker.log

# Reload nginx
sudo /opt/nginx/sbin/nginx -t && sudo /opt/nginx/sbin/nginx -s reload

# Manual deployment (if needed)
cd /var/www/pos/backend
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
export DJANGO_ENV_FILE=/var/www/pos/backend/.env.production
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn celery celery-beat
```
