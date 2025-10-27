# Deployment Scripts and Configuration

This directory contains all the necessary files and scripts for deploying the POS Backend application to production.

## Directory Contents

### Configuration Files

- **`gunicorn.service`** - Systemd service file for Gunicorn WSGI server
- **`celery.service`** - Systemd service file for Celery worker
- **`celery-beat.service`** - Systemd service file for Celery beat scheduler

### Deployment Scripts

- **`initial_setup.sh`** - Complete server setup script (run once)
- **`deploy.sh`** - Manual deployment script
- **`ssl_setup.sh`** - SSL certificate setup using Let's Encrypt
- **`health_check.sh`** - System health verification script
- **`pre_deployment_check.sh`** - Pre-deployment checklist validation

### Documentation

- **`DEPLOYMENT_GUIDE.md`** - Comprehensive deployment guide
- **`QUICK_REFERENCE.md`** - Quick reference for common operations
- **`README.md`** - This file

## Quick Start

### First Time Deployment

1. **Prepare your local repository:**
   ```bash
   # Make scripts executable
   chmod +x deployment/*.sh
   
   # Run pre-deployment check
   ./deployment/pre_deployment_check.sh
   
   # Commit and push to GitHub
   git add .
   git commit -m "Add deployment configuration"
   git push origin main
   ```

2. **On your VPS:**
   ```bash
   # SSH into server
   ssh -p 7822 deploy@68.66.251.79
   
   # Navigate to project directory
   cd /var/www/pos/backend
   
   # Clone repository (if not already done)
   git clone YOUR_REPO_URL .
   
   # Make scripts executable
   chmod +x deployment/*.sh
   
   # Run initial setup
   ./deployment/initial_setup.sh
   ```

3. **Configure environment:**
   ```bash
   # Edit production environment file
   nano .env.production
   
   # Update with your actual values:
   # - SECRET_KEY
   # - Database credentials
   # - Domain names
   # - Email settings, etc.
   ```

4. **Start services:**
   ```bash
   sudo systemctl start posbackend
   sudo systemctl start posbackend-celery
   sudo systemctl start posbackend-celery-beat
   ```

5. **Set up SSL (optional but recommended):**
   ```bash
   ./deployment/ssl_setup.sh
   ```

### Subsequent Deployments

#### Using CI/CD (Recommended):
```bash
# On your local machine
git add .
git commit -m "Your changes"
git push origin main
# GitHub Actions will automatically deploy
```

#### Manual Deployment:
```bash
# SSH into server
ssh -p 7822 deploy@68.66.251.79

# Run deployment script
cd /var/www/pos/backend
./deployment/deploy.sh
```

## Script Descriptions

### initial_setup.sh
**Purpose:** Complete first-time server setup  
**When to use:** Only once when setting up a new server  
**What it does:**
- Installs system dependencies
- Sets up PostgreSQL database
- Creates Python virtual environment
- Configures systemd services
- Sets up Nginx
- Sets proper permissions

**Usage:**
```bash
./deployment/initial_setup.sh
```

### deploy.sh
**Purpose:** Deploy code updates  
**When to use:** For manual deployments after code changes  
**What it does:**
- Pulls latest code from Git
- Updates Python dependencies
- Runs database migrations
- Collects static files
- Restarts services

**Usage:**
```bash
./deployment/deploy.sh
```

### ssl_setup.sh
**Purpose:** Set up HTTPS with Let's Encrypt  
**When to use:** After DNS is configured and pointing to your server  
**What it does:**
- Installs Certbot
- Obtains SSL certificate
- Configures Nginx for HTTPS
- Sets up auto-renewal

**Usage:**
```bash
./deployment/ssl_setup.sh
```

### health_check.sh
**Purpose:** Verify system health  
**When to use:** To check if all services are running correctly  
**What it does:**
- Checks all services status
- Verifies network ports
- Checks disk space
- Tests application response
- Reviews recent errors

**Usage:**
```bash
./deployment/health_check.sh
```

### pre_deployment_check.sh
**Purpose:** Validate configuration before deployment  
**When to use:** Before deploying to production  
**What it does:**
- Checks configuration files exist
- Validates Django settings
- Verifies security settings
- Checks dependencies
- Reviews Git status

**Usage:**
```bash
./deployment/pre_deployment_check.sh
```

## Systemd Service Files

### gunicorn.service
Manages the Gunicorn WSGI server that runs your Django application.

**Copy to:** `/etc/systemd/system/posbackend.service`

**Commands:**
```bash
sudo systemctl start posbackend
sudo systemctl stop posbackend
sudo systemctl restart posbackend
sudo systemctl status posbackend
```

### celery.service
Manages the Celery worker for background tasks.

**Copy to:** `/etc/systemd/system/posbackend-celery.service`

**Commands:**
```bash
sudo systemctl start posbackend-celery
sudo systemctl stop posbackend-celery
sudo systemctl restart posbackend-celery
sudo systemctl status posbackend-celery
```

### celery-beat.service
Manages the Celery beat scheduler for periodic tasks.

**Copy to:** `/etc/systemd/system/posbackend-celery-beat.service`

**Commands:**
```bash
sudo systemctl start posbackend-celery-beat
sudo systemctl stop posbackend-celery-beat
sudo systemctl restart posbackend-celery-beat
sudo systemctl status posbackend-celery-beat
```

## Common Tasks

### Update Environment Variables
```bash
nano /var/www/pos/backend/.env.production
sudo systemctl restart posbackend
```

### View Logs
```bash
# Application logs
tail -f /var/www/pos/backend/logs/gunicorn_error.log

# System logs
sudo journalctl -u posbackend -f
```

### Database Migration
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py migrate
```

### Collect Static Files
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py collectstatic --noinput
```

### Create Superuser
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py createsuperuser
```

### Database Backup
```bash
pg_dump -U pos_user pos_production > backup_$(date +%Y%m%d_%H%M%S).sql
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u posbackend -n 50 --no-pager

# Check socket file
ls -la /var/www/pos/backend/gunicorn.sock

# Restart service
sudo systemctl restart posbackend
```

### 502 Bad Gateway
Usually means Gunicorn isn't running:
```bash
sudo systemctl status posbackend
sudo systemctl restart posbackend
```

### Static Files Not Loading
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py collectstatic --clear --noinput
```

### Check All Services
```bash
./deployment/health_check.sh
```

## Security Checklist

Before going live:
- [ ] Change SECRET_KEY to a strong random value
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS properly
- [ ] Set up SSL/HTTPS
- [ ] Change default database password
- [ ] Configure firewall (UFW)
- [ ] Set up fail2ban for SSH protection
- [ ] Enable automated backups
- [ ] Review CORS settings

## File Permissions

The deployment scripts will set these automatically, but for reference:

```bash
sudo chown -R deploy:www-data /var/www/pos/backend
sudo chmod -R 755 /var/www/pos/backend
sudo chmod -R 775 /var/www/pos/backend/logs
sudo chmod -R 775 /var/www/pos/backend/media
```

## Environment Variables

Key variables to set in `.env.production`:

**Required:**
- `SECRET_KEY` - Django secret key
- `DB_NAME` - Database name
- `DB_USER` - Database user
- `DB_PASSWORD` - Database password
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts

**Recommended:**
- `DEBUG` - Set to `False` in production
- `REDIS_URL` - Redis connection URL
- `EMAIL_HOST` - SMTP server
- `EMAIL_HOST_USER` - Email username
- `EMAIL_HOST_PASSWORD` - Email password

See `.env.production.example` for all available options.

## Support

For detailed information, see:
- [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md) - Quick command reference

## CI/CD with GitHub Actions

The GitHub Actions workflow is configured in `.github/workflows/deploy.yml`.

**Required GitHub Secrets:**
- `VPS_HOST` - Your server IP (68.66.251.79)
- `VPS_USERNAME` - SSH username (deploy)
- `VPS_PORT` - SSH port (7822)
- `SSH_PRIVATE_KEY` - SSH private key for authentication

**Workflow triggers:**
- Automatically on push to `main` branch
- Manually via GitHub Actions UI

## Notes

- All scripts assume the project is at `/var/www/pos/backend`
- Scripts require the `deploy` user to have sudo privileges
- Some operations may require password input
- Always test in a staging environment first
- Keep backups before major changes

---

**Last Updated:** October 2025  
**Maintainer:** POS Development Team
