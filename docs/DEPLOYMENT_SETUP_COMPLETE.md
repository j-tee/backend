# 🚀 POS Backend - Complete CI/CD Deployment Setup

## ✅ What Has Been Set Up

I've created a complete CI/CD deployment infrastructure for your Django POS backend application. Here's everything that's been configured:

### 📁 Files Created

#### 1. **CI/CD Configuration**
- `.github/workflows/deploy.yml` - GitHub Actions workflow for automated deployment

#### 2. **Server Configuration**
- `nginx.conf` - Nginx web server configuration
- `.env.production.example` - Template for production environment variables

#### 3. **System Service Files**
- `deployment/gunicorn.service` - Gunicorn WSGI server service
- `deployment/celery.service` - Celery worker service
- `deployment/celery-beat.service` - Celery beat scheduler service

#### 4. **Deployment Scripts**
- `deployment/initial_setup.sh` - First-time server setup
- `deployment/deploy.sh` - Manual deployment script
- `deployment/ssl_setup.sh` - SSL certificate setup
- `deployment/health_check.sh` - System health verification
- `deployment/pre_deployment_check.sh` - Pre-deployment validation

#### 5. **Documentation**
- `deployment/DEPLOYMENT_GUIDE.md` - Comprehensive deployment guide (2000+ lines)
- `deployment/QUICK_REFERENCE.md` - Quick command reference
- `deployment/README.md` - Deployment folder documentation

---

## 🎯 Next Steps - Your Action Plan

### Step 1: Prepare Your GitHub Repository

```bash
# 1. Update the GitHub workflow with your repo URL
# Edit .github/workflows/deploy.yml, line 75
# Replace YOUR_USERNAME/YOUR_REPO.git with your actual repository

# 2. Update initial setup script
# Edit deployment/initial_setup.sh, line 30
# Replace YOUR_USERNAME/YOUR_REPO.git with your actual repository

# 3. Commit all changes
git add .
git commit -m "Add CI/CD deployment configuration"

# 4. Push to GitHub (if not already pushed)
git push origin development

# 5. Merge to main branch for production deployment
# You can do this via GitHub Pull Request
```

### Step 2: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `VPS_HOST` | `68.66.251.79` | Your VPS IP address |
| `VPS_USERNAME` | `deploy` | SSH username |
| `VPS_PORT` | `7822` | SSH port |
| `SSH_PRIVATE_KEY` | [Your SSH private key] | Private key to access VPS |

**To get your SSH private key:**
```bash
# On your local machine
cat ~/.ssh/id_ed25519  # or id_rsa, or whatever key you use
# Copy the entire output including BEGIN and END lines
```

### Step 3: Set Up SSH Keys on Server

Since you mentioned you have some GitHub setups but can't remember the details, let's set up a fresh SSH key:

```bash
# 1. SSH into your server
ssh -p 7822 deploy@68.66.251.79

# 2. Generate a new SSH key specifically for this project
ssh-keygen -t ed25519 -C "pos-backend-deploy" -f ~/.ssh/github_pos_backend

# 3. Start SSH agent and add the key
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/github_pos_backend

# 4. Display the public key
cat ~/.ssh/github_pos_backend.pub
```

**Add this public key to GitHub:**
- Go to your GitHub repository → Settings → Deploy keys
- Click "Add deploy key"
- Give it a title like "Production Server Deploy Key"
- Paste the public key
- ✅ Check "Allow write access" (needed for CI/CD)
- Click "Add key"

**Configure Git to use this key:**
```bash
# Create/edit SSH config on server
nano ~/.ssh/config

# Add these lines:
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_pos_backend
    IdentitiesOnly yes

# Save and exit (Ctrl+X, Y, Enter)

# Set correct permissions
chmod 600 ~/.ssh/config

# Test the connection
ssh -T git@github.com
# You should see: "Hi USERNAME! You've successfully authenticated..."
```

### Step 4: Initial Server Setup

**On your VPS:**

```bash
# 1. Navigate to project directory
cd /var/www/pos/backend

# 2. Clone your repository (if not already done)
# Replace with your actual repository URL
git clone git@github.com:YOUR_USERNAME/YOUR_REPO.git .

# 3. Checkout main branch
git checkout main  # or development if testing first

# 4. Make scripts executable
chmod +x deployment/*.sh

# 5. Run the initial setup script
./deployment/initial_setup.sh
```

This will take 5-10 minutes and will:
- ✅ Install all system dependencies (PostgreSQL, Redis, Nginx, etc.)
- ✅ Create PostgreSQL database
- ✅ Set up Python virtual environment
- ✅ Install Python packages
- ✅ Configure systemd services
- ✅ Set up Nginx
- ✅ Set proper file permissions

### Step 5: Configure Production Environment

```bash
# Edit the production environment file
nano /var/www/pos/backend/.env.production
```

**Critical settings to update:**

```env
# Generate a strong secret key
SECRET_KEY=your-strong-secret-key-here

# Database credentials (match what you set in PostgreSQL)
DB_NAME=pos_production
DB_USER=pos_user
DB_PASSWORD=your-strong-database-password

# Your domain and IP
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,68.66.251.79

# Frontend URL (update when you deploy frontend)
FRONTEND_URL=https://your-frontend-domain.com
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com

# Email settings (if using email)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# Set to False in production
DEBUG=False
BYPASS_SUBSCRIPTION_CHECK=False
```

**Generate a secret key:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 6: Update Nginx Configuration

```bash
# Edit Nginx config
sudo nano /etc/nginx/sites-available/posbackend

# Find this line:
server_name your-domain.com www.your-domain.com;

# Replace with your actual domain or IP:
server_name yourdomain.com www.yourdomain.com 68.66.251.79;

# Save and test
sudo nginx -t

# If test passes, reload using our smart script
./deployment/nginx_control.sh reload
```

**Note:** If your Nginx was compiled from source (not installed via apt), see `deployment/NGINX_SOURCE_SETUP.md` for setup options. Our scripts auto-detect and work with any Nginx installation method.

### Step 7: Start Services

```bash
# Start all services
sudo systemctl start posbackend
sudo systemctl start posbackend-celery
sudo systemctl start posbackend-celery-beat

# Check status
sudo systemctl status posbackend
sudo systemctl status posbackend-celery
sudo systemctl status posbackend-celery-beat

# View logs
tail -f /var/www/pos/backend/logs/gunicorn_error.log
```

### Step 8: Test Your Deployment

```bash
# Run health check
./deployment/health_check.sh

# Test from browser
# Visit: http://68.66.251.79
# Or: http://yourdomain.com (if DNS is configured)
```

### Step 9: Set Up SSL (Recommended)

**After your domain DNS is pointing to your server:**

```bash
./deployment/ssl_setup.sh
```

This will:
- Install Certbot
- Obtain SSL certificate from Let's Encrypt
- Configure Nginx for HTTPS
- Set up automatic renewal

### Step 10: Enable CI/CD

Once everything is working manually:

```bash
# On your local machine
git add .
git commit -m "Your changes"
git push origin main

# GitHub Actions will automatically:
# 1. Run tests
# 2. Deploy to your VPS if tests pass
# 3. Restart services
```

---

## 📋 Deployment Workflow

### Manual Deployment
```bash
ssh -p 7822 deploy@68.66.251.79
cd /var/www/pos/backend
./deployment/deploy.sh
```

### Automatic Deployment (CI/CD)
```bash
# Just push to main branch
git push origin main
# GitHub Actions handles the rest!
```

---

## 🔍 Important Server Details

| Item | Value |
|------|-------|
| **VPS IP** | 68.66.251.79 |
| **SSH Port** | 7822 |
| **SSH User** | deploy |
| **Project Path** | /var/www/pos/backend |
| **Python** | 3.11 |
| **Database** | PostgreSQL 15 |
| **Web Server** | Nginx |
| **App Server** | Gunicorn |
| **Task Queue** | Celery + Redis |

---

## 🔧 Common Commands

### Service Management
```bash
# Restart application
sudo systemctl restart posbackend

# View logs
tail -f logs/gunicorn_error.log
sudo journalctl -u posbackend -f

# Check status
sudo systemctl status posbackend
```

### Django Management
```bash
# Activate environment
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### Database
```bash
# Access database
sudo -u postgres psql -d pos_production -U pos_user

# Backup database
pg_dump -U pos_user pos_production > backup.sql

# Restore database
psql -U pos_user pos_production < backup.sql
```

---

## 🚨 Troubleshooting

### Service Won't Start
```bash
sudo journalctl -u posbackend -n 50 --no-pager
tail -f logs/gunicorn_error.log
```

### 502 Bad Gateway
```bash
sudo systemctl restart posbackend
ls -la gunicorn.sock
```

### Database Connection Failed
```bash
sudo systemctl status postgresql
cat .env.production | grep DB_
```

### Run Full Health Check
```bash
./deployment/health_check.sh
```

---

## 📚 Documentation Reference

- **`deployment/DEPLOYMENT_GUIDE.md`** - Complete step-by-step guide
- **`deployment/QUICK_REFERENCE.md`** - Common commands
- **`deployment/README.md`** - Deployment folder overview

---

## ✅ Pre-Deployment Checklist

Before going live, ensure:

- [ ] GitHub repository is set up
- [ ] GitHub Secrets are configured
- [ ] SSH keys are set up on server
- [ ] `.env.production` is properly configured
- [ ] Database is created and accessible
- [ ] Nginx configuration is updated with your domain
- [ ] All services start successfully
- [ ] Health check passes
- [ ] SSL certificate is installed (if using HTTPS)
- [ ] Firewall is configured (UFW)
- [ ] Automated backups are set up

---

## 🎉 What You Get

✅ **Automated Testing** - Tests run on every push  
✅ **Automated Deployment** - Deploy by pushing to main  
✅ **Zero-Downtime Deployment** - Services reload gracefully  
✅ **Logging** - Comprehensive application and system logs  
✅ **Monitoring** - Health check script  
✅ **Security** - HTTPS with Let's Encrypt  
✅ **Scalability** - Gunicorn workers, Celery for background tasks  
✅ **Professional Setup** - Production-ready configuration  

---

## 🆘 Need Help?

If you encounter issues:

1. **Check the logs:**
   ```bash
   ./deployment/health_check.sh
   tail -f logs/gunicorn_error.log
   ```

2. **Review documentation:**
   - `deployment/DEPLOYMENT_GUIDE.md` - Detailed guide
   - `deployment/QUICK_REFERENCE.md` - Common commands
   - `deployment/README.md` - Scripts overview

3. **Common fixes:**
   - Restart services: `sudo systemctl restart posbackend`
   - Check permissions: `sudo chown -R deploy:www-data /var/www/pos/backend`
   - Verify environment: `cat .env.production`

---

## 🚀 You're Ready to Deploy!

Everything is set up and ready. Follow the steps above, and you'll have a production-ready Django application with CI/CD in about 30-60 minutes.

**Good luck with your deployment! 🎉**

---

*Created: October 27, 2025*  
*Last Updated: October 27, 2025*
