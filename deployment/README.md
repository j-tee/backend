# Deployment Scripts

This folder contains all scripts and configurations needed for deploying the POS Backend application.

## 📁 Contents

### Shell Scripts (Executable)
- **`initial_setup.sh`** - Complete first-time server setup (run once)
- **`deploy.sh`** - Manual deployment script for updates
- **`ssl_setup.sh`** - SSL certificate setup with Let's Encrypt
- **`health_check.sh`** - System health verification
- **`pre_deployment_check.sh`** - Pre-deployment validation
- **`nginx_control.sh`** - Universal Nginx controller (systemd/init.d/source-compiled)
- **`check_nginx.sh`** - Diagnostic tool for Nginx installation

### Service Configuration Files
- **`gunicorn.service`** - Systemd service for Gunicorn WSGI server
- **`celery.service`** - Systemd service for Celery worker
- **`celery-beat.service`** - Systemd service for Celery beat scheduler

## 📖 Documentation

All deployment documentation has been moved to the [`docs/`](../docs/) folder:

- **[DEPLOYMENT_SETUP_COMPLETE.md](../docs/DEPLOYMENT_SETUP_COMPLETE.md)** ⭐ **START HERE** - Complete action plan
- **[DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md)** - Comprehensive step-by-step guide
- **[QUICK_REFERENCE.md](../docs/QUICK_REFERENCE.md)** - Common commands reference
- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System architecture diagrams
- **[DEPLOYMENT_README.md](../docs/DEPLOYMENT_README.md)** - Deployment scripts documentation
- **[NGINX_SOURCE_SETUP.md](../docs/NGINX_SOURCE_SETUP.md)** - Nginx setup for source-compiled installations
- **[NGINX_FIX_SUMMARY.md](../docs/NGINX_FIX_SUMMARY.md)** - Nginx compatibility updates
- **[NGINX_IMPORTANT_NOTE.md](../docs/NGINX_IMPORTANT_NOTE.md)** - Important Nginx notes

## 🚀 Quick Start

### First Time Deployment

1. **On your local machine:**
   ```bash
   # Make scripts executable
   chmod +x deployment/*.sh
   
   # Commit and push
   git add .
   git commit -m "Add deployment configuration"
   git push origin main
   ```

2. **On your VPS:**
   ```bash
   # Clone repository
   cd /var/www/pos/backend
   git clone YOUR_REPO_URL .
   
   # Make scripts executable
   chmod +x deployment/*.sh
   
   # Run initial setup
   ./deployment/initial_setup.sh
   ```

3. **Configure environment:**
   ```bash
   nano .env.production
   # Update with your settings
   ```

4. **Start services:**
   ```bash
   sudo systemctl start posbackend
   sudo systemctl start posbackend-celery
   sudo systemctl start posbackend-celery-beat
   ```

### Subsequent Deployments

**Using CI/CD (Recommended):**
```bash
git push origin main  # Auto-deploys via GitHub Actions
```

**Manual Deployment:**
```bash
ssh -p 7822 deploy@YOUR_SERVER_IP
cd /var/www/pos/backend
./deployment/deploy.sh
```

## 🔍 Script Descriptions

### initial_setup.sh
**When:** First-time server setup only  
**What it does:**
- Installs system dependencies
- Creates PostgreSQL database
- Sets up Python virtual environment
- Configures systemd services
- Sets up Nginx
- Sets permissions

### deploy.sh
**When:** After code updates  
**What it does:**
- Pulls latest code
- Updates dependencies
- Runs migrations
- Collects static files
- Restarts services

### nginx_control.sh
**When:** Anytime you need to control Nginx  
**What it does:**
- Auto-detects Nginx management method
- Provides unified interface (start/stop/restart/reload)
- Works with systemd, init.d, or source-compiled Nginx

**Usage:**
```bash
./deployment/nginx_control.sh test      # Test configuration
./deployment/nginx_control.sh reload    # Reload configuration
./deployment/nginx_control.sh restart   # Restart Nginx
./deployment/nginx_control.sh status    # Check status
```

### health_check.sh
**When:** To verify system health  
**What it does:**
- Checks all services status
- Verifies network ports
- Checks disk space
- Tests application response
- Reviews recent errors

### check_nginx.sh
**When:** To diagnose Nginx setup  
**What it does:**
- Detects Nginx installation method
- Shows Nginx version and paths
- Indicates how Nginx is managed
- Suggests control commands

### ssl_setup.sh
**When:** After DNS is configured  
**What it does:**
- Installs Certbot
- Obtains SSL certificate
- Configures Nginx for HTTPS
- Sets up auto-renewal

### pre_deployment_check.sh
**When:** Before deploying to production  
**What it does:**
- Validates configuration files
- Checks Django settings
- Verifies dependencies
- Reviews security settings
- Checks Git status

## 🛠️ Service Files

Copy these to `/etc/systemd/system/` during initial setup:

- `gunicorn.service` → `/etc/systemd/system/posbackend.service`
- `celery.service` → `/etc/systemd/system/posbackend-celery.service`
- `celery-beat.service` → `/etc/systemd/system/posbackend-celery-beat.service`

**Service commands:**
```bash
sudo systemctl start posbackend
sudo systemctl stop posbackend
sudo systemctl restart posbackend
sudo systemctl status posbackend
sudo systemctl enable posbackend  # Start on boot
```

## 📋 Common Tasks

### Update environment variables
```bash
nano /var/www/pos/backend/.env.production
sudo systemctl restart posbackend
```

### View logs
```bash
tail -f /var/www/pos/backend/logs/gunicorn_error.log
sudo journalctl -u posbackend -f
```

### Run migrations
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py migrate
```

### Create superuser
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py createsuperuser
```

## ⚠️ Important Notes

### Nginx Source-Compiled Support
If your Nginx was compiled from source (not installed via apt), the scripts automatically detect this and use the appropriate control method. See [NGINX_SOURCE_SETUP.md](../docs/NGINX_SOURCE_SETUP.md) for details.

### File Permissions
Scripts automatically set correct permissions:
```bash
sudo chown -R deploy:www-data /var/www/pos/backend
sudo chmod -R 755 /var/www/pos/backend
sudo chmod -R 775 /var/www/pos/backend/logs
sudo chmod -R 775 /var/www/pos/backend/media
```

### Environment Variables
Always use `.env.production` in production. Never commit `.env` files to Git!

## 🔒 Security Checklist

Before going live:
- [ ] Change SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS
- [ ] Set up SSL/HTTPS
- [ ] Change database password
- [ ] Configure firewall
- [ ] Set up fail2ban
- [ ] Enable automated backups

## 📞 Need Help?

See the documentation in [`docs/`](../docs/):
- Troubleshooting guide
- Architecture diagrams
- Quick reference
- Complete deployment guide

---

**All scripts are tested and production-ready!**
