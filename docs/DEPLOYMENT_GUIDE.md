# POS Backend Deployment Guide

This guide will walk you through deploying your Django POS backend application to your VPS using CI/CD with GitHub Actions.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Server Initial Setup](#server-initial-setup)
3. [GitHub Repository Setup](#github-repository-setup)
4. [CI/CD Configuration](#cicd-configuration)
5. [Manual Deployment](#manual-deployment)
6. [SSL Setup](#ssl-setup)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### On Your VPS
- Ubuntu 22.04 LTS
- User: `deploy` with sudo privileges
- SSH access on port 7822
- IP: 68.66.251.79
- Directory structure: `/var/www/pos/backend`

### On Your Local Machine
- Git installed
- SSH access to your VPS
- GitHub account

## Server Initial Setup

### Step 1: Connect to Your Server

```bash
ssh -p 7822 deploy@68.66.251.79
```

### Step 2: Ensure Deploy User Has Proper Permissions

```bash
# Add deploy user to www-data group
sudo usermod -a -G www-data deploy

# Ensure proper ownership
sudo chown -R deploy:www-data /var/www/pos/backend
```

### Step 3: Set Up SSH Key for GitHub

If you don't have an SSH key or can't remember which one is configured:

```bash
# Check existing SSH keys
ls -la ~/.ssh

# Generate a new SSH key if needed
ssh-keygen -t ed25519 -C "deploy@your-server" -f ~/.ssh/github_pos

# Start SSH agent
eval "$(ssh-agent -s)"

# Add key to agent
ssh-add ~/.ssh/github_pos

# Display public key to add to GitHub
cat ~/.ssh/github_pos.pub
```

**Add this public key to your GitHub repository:**
1. Go to GitHub → Your Repository → Settings → Deploy Keys
2. Click "Add deploy key"
3. Paste the public key
4. Check "Allow write access" (needed for status updates)
5. Save

### Step 4: Configure Git on Server

```bash
git config --global user.name "Deploy Bot"
git config --global user.email "deploy@your-domain.com"

# Test GitHub connection
ssh -T git@github.com
```

### Step 5: Clone Repository

```bash
cd /var/www/pos/backend

# Clone your repository (replace with your actual repo URL)
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git .

# Checkout main branch
git checkout main
```

### Step 6: Run Initial Setup Script

```bash
# Make script executable
chmod +x deployment/initial_setup.sh

# Run setup
./deployment/initial_setup.sh
```

This script will:
- Install all system dependencies
- Set up PostgreSQL database
- Create Python virtual environment
- Install Python packages
- Set up systemd services
- Configure Nginx
- Set proper file permissions

### Step 7: Configure Environment Variables

```bash
# Edit production environment file
nano .env.production
```

**Important settings to update:**
- `SECRET_KEY` - Generate a strong secret key
- `DB_PASSWORD` - Match the password you set in PostgreSQL
- `ALLOWED_HOSTS` - Add your domain and IP
- `CORS_ALLOWED_ORIGINS` - Add your frontend URL
- Email settings (if using email features)
- Payment gateway keys (when ready)

**Generate a secret key:**
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 8: Update Nginx Configuration

```bash
# Edit nginx config
sudo nano /etc/nginx/sites-available/posbackend
```

Update `server_name` with your actual domain or IP address.

```bash
# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### Step 9: Start Services

```bash
# Start all services
sudo systemctl start posbackend
sudo systemctl start posbackend-celery
sudo systemctl start posbackend-celery-beat

# Check status
sudo systemctl status posbackend
sudo systemctl status posbackend-celery
sudo systemctl status posbackend-celery-beat
```

### Step 10: Test Deployment

```bash
# Check if server is responding
curl http://localhost:8000/health/  # If you have a health endpoint
curl http://YOUR_SERVER_IP/

# Check logs
tail -f logs/gunicorn_error.log
tail -f logs/gunicorn_access.log
```

## GitHub Repository Setup

### Step 1: Push Your Code to GitHub

On your local machine:

```bash
cd /home/teejay/Documents/Projects/pos/backend

# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - ready for deployment"

# Add remote (replace with your repo URL)
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git

# Push to main branch
git push -u origin main
```

### Step 2: Configure GitHub Secrets

Go to GitHub → Your Repository → Settings → Secrets and variables → Actions

Add the following secrets:

1. **VPS_HOST**: `68.66.251.79`
2. **VPS_USERNAME**: `deploy`
3. **VPS_PORT**: `7822`
4. **SSH_PRIVATE_KEY**: Your SSH private key

To get your SSH private key:

```bash
# On your local machine
cat ~/.ssh/id_ed25519  # or whatever key you use to access the VPS
```

Copy the entire output including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`

**⚠️ SECURITY NOTE:** This private key should be the one that can access your VPS as the `deploy` user.

## CI/CD Configuration

The GitHub Actions workflow (`.github/workflows/deploy.yml`) is already configured. It will:

1. **On every push to `main` branch:**
   - Run tests
   - Deploy to your VPS if tests pass

2. **Deployment steps:**
   - SSH into your VPS
   - Pull latest code
   - Install dependencies
   - Run migrations
   - Collect static files
   - Restart services

### Triggering Deployment

Simply push to the main branch:

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

Check the deployment status in GitHub → Your Repository → Actions

## Manual Deployment

If you need to deploy manually without CI/CD:

```bash
# SSH into server
ssh -p 7822 deploy@68.66.251.79

# Navigate to project
cd /var/www/pos/backend

# Run deployment script
./deployment/deploy.sh
```

## SSL Setup

Once your domain is pointing to your server:

```bash
# Make script executable
chmod +x deployment/ssl_setup.sh

# Run SSL setup
./deployment/ssl_setup.sh
```

This will:
- Install Certbot
- Obtain SSL certificate from Let's Encrypt
- Configure Nginx for HTTPS
- Set up automatic renewal

After SSL is set up:
1. Edit `/etc/nginx/sites-available/posbackend`
2. Uncomment the HTTPS server block
3. Restart Nginx: `sudo systemctl restart nginx`

## Monitoring and Maintenance

### Service Management

```bash
# Check service status
sudo systemctl status posbackend
sudo systemctl status posbackend-celery
sudo systemctl status posbackend-celery-beat
sudo systemctl status nginx

# Restart services
sudo systemctl restart posbackend
sudo systemctl restart posbackend-celery
sudo systemctl restart posbackend-celery-beat
sudo systemctl reload nginx

# View logs
sudo journalctl -u posbackend -f
sudo journalctl -u posbackend-celery -f
tail -f /var/www/pos/backend/logs/gunicorn_error.log
tail -f /var/www/pos/backend/logs/celery_worker.log
```

### Database Backup

Create a backup script:

```bash
#!/bin/bash
# Save as /var/www/pos/backend/deployment/backup.sh

BACKUP_DIR="/var/www/pos/backend/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/pos_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U pos_user pos_production > $BACKUP_FILE

# Compress
gzip $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"
```

Set up daily backups with cron:

```bash
crontab -e

# Add this line to run backup daily at 2 AM
0 2 * * * /var/www/pos/backend/deployment/backup.sh
```

### Monitoring Disk Space

```bash
# Check disk usage
df -h

# Check largest directories
du -sh /var/www/pos/backend/*
```

### Log Rotation

Create log rotation configuration:

```bash
sudo nano /etc/logrotate.d/posbackend
```

Add:

```
/var/www/pos/backend/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 deploy www-data
    sharedscripts
    postrotate
        sudo systemctl reload posbackend > /dev/null 2>&1 || true
    endscript
}
```

## Troubleshooting

### Service Won't Start

```bash
# Check detailed error logs
sudo journalctl -u posbackend -n 50 --no-pager

# Check if port is already in use
sudo lsof -i :8000

# Check socket file
ls -la /var/www/pos/backend/gunicorn.sock

# Check file permissions
ls -la /var/www/pos/backend
```

### Database Connection Issues

```bash
# Test database connection
sudo -u postgres psql -d pos_production -U pos_user

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check database credentials in .env.production
cat .env.production | grep DB_
```

### Static Files Not Loading

```bash
# Collect static files again
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py collectstatic --noinput

# Check permissions
ls -la staticfiles/

# Check Nginx configuration
sudo nginx -t
```

### CI/CD Deployment Fails

1. **Check GitHub Actions logs** in your repository
2. **Verify SSH connection from GitHub:**
   - Ensure SSH_PRIVATE_KEY secret is correct
   - Check VPS firewall allows connections
3. **Check deployment script permissions:**
   ```bash
   chmod +x deployment/deploy.sh
   ```

### 502 Bad Gateway

This usually means Gunicorn isn't running:

```bash
# Check if Gunicorn is running
sudo systemctl status posbackend

# Check if socket file exists
ls -la /var/www/pos/backend/gunicorn.sock

# Restart the service
sudo systemctl restart posbackend

# Check logs
tail -f logs/gunicorn_error.log
```

### Celery Tasks Not Running

```bash
# Check Celery worker status
sudo systemctl status posbackend-celery

# Check Redis is running
sudo systemctl status redis

# Test Redis connection
redis-cli ping

# Check Celery logs
tail -f logs/celery_worker.log
```

## Performance Optimization

### Increase Gunicorn Workers

Edit `/etc/systemd/system/posbackend.service`:

```ini
# Rule of thumb: (2 x $num_cores) + 1
--workers 5
```

### Enable Nginx Caching

Add to your Nginx config:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=pos_cache:10m max_size=100m;

location / {
    proxy_cache pos_cache;
    proxy_cache_valid 200 10m;
    # ... other settings
}
```

### Database Connection Pooling

Install pgbouncer for better database connection management.

## Security Checklist

- [ ] Change default PostgreSQL password
- [ ] Set strong SECRET_KEY in production
- [ ] Enable firewall (UFW)
- [ ] Set up SSL/HTTPS
- [ ] Configure fail2ban for SSH protection
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`
- [ ] Set up automated backups
- [ ] Enable DEBUG=False in production
- [ ] Configure proper ALLOWED_HOSTS
- [ ] Set secure CORS_ALLOWED_ORIGINS

## Additional Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)

## Support

If you encounter issues:
1. Check the logs (Gunicorn, Celery, Nginx, System)
2. Review this troubleshooting section
3. Check Django documentation
4. Review your .env.production configuration

---

**Congratulations! Your POS backend is now deployed with CI/CD! 🎉**
