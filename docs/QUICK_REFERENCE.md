# Quick Reference Guide for Common Operations

## Service Management

### Check Service Status
```bash
sudo systemctl status posbackend
sudo systemctl status posbackend-celery
sudo systemctl status posbackend-celery-beat
sudo systemctl status nginx
```

### Restart Services
```bash
sudo systemctl restart posbackend
sudo systemctl restart posbackend-celery
sudo systemctl restart posbackend-celery-beat
sudo systemctl reload nginx  # Reload without dropping connections
```

### Stop Services
```bash
sudo systemctl stop posbackend
sudo systemctl stop posbackend-celery
sudo systemctl stop posbackend-celery-beat
```

### Start Services
```bash
sudo systemctl start posbackend
sudo systemctl start posbackend-celery
sudo systemctl start posbackend-celery-beat
```

## Log Viewing

### Real-time Logs
```bash
# Gunicorn logs
tail -f /var/www/pos/backend/logs/gunicorn_error.log
tail -f /var/www/pos/backend/logs/gunicorn_access.log

# Celery logs
tail -f /var/www/pos/backend/logs/celery_worker.log
tail -f /var/www/pos/backend/logs/celery_beat.log

# System logs
sudo journalctl -u posbackend -f
sudo journalctl -u posbackend-celery -f

# Nginx logs
sudo tail -f /var/log/nginx/posbackend_error.log
sudo tail -f /var/log/nginx/posbackend_access.log
```

### View Last N Lines
```bash
tail -n 100 /var/www/pos/backend/logs/gunicorn_error.log
sudo journalctl -u posbackend -n 50 --no-pager
```

## Deployment

### Manual Deployment
```bash
ssh -p 7822 deploy@68.66.251.79
cd /var/www/pos/backend
./deployment/deploy.sh
```

### Quick Update (without script)
```bash
cd /var/www/pos/backend
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart posbackend
```

### Auto Deployment via CI/CD
```bash
# On your local machine
git add .
git commit -m "Your message"
git push origin main
# GitHub Actions will automatically deploy
```

## Database Operations

### Access Database
```bash
sudo -u postgres psql -d pos_production -U pos_user
```

### Run Migrations
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py migrate
```

### Create Database Backup
```bash
pg_dump -U pos_user pos_production > backup_$(date +%Y%m%d).sql
```

### Restore Database Backup
```bash
psql -U pos_user pos_production < backup_20241027.sql
```

### Django Shell
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py shell
```

## Django Management Commands

### Create Superuser
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py createsuperuser
```

### Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### Check Deployment Settings
```bash
python manage.py check --deploy
```

### Clear Cache (if using Redis)
```bash
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

## File Permissions

### Fix Permissions
```bash
cd /var/www/pos
sudo chown -R deploy:www-data backend/
sudo chmod -R 755 backend/
sudo chmod -R 775 backend/logs/
sudo chmod -R 775 backend/media/
```

### Make Scripts Executable
```bash
chmod +x deployment/*.sh
```

## Environment Management

### Edit Production Environment
```bash
nano /var/www/pos/backend/.env.production
# After changes, restart services
sudo systemctl restart posbackend
```

### View Current Settings (without secrets)
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py diffsettings
```

## Nginx Operations

### Test Configuration
```bash
sudo nginx -t
```

### Reload Configuration
```bash
sudo systemctl reload nginx
```

### View Available Sites
```bash
ls -la /etc/nginx/sites-available/
ls -la /etc/nginx/sites-enabled/
```

### Edit Nginx Config
```bash
sudo nano /etc/nginx/sites-available/posbackend
sudo nginx -t
sudo systemctl reload nginx
```

## SSL/HTTPS

### Renew Certificate
```bash
sudo certbot renew
```

### Test Renewal
```bash
sudo certbot renew --dry-run
```

### Certificate Status
```bash
sudo certbot certificates
```

## Monitoring

### Check Disk Space
```bash
df -h
du -sh /var/www/pos/backend/*
```

### Check Memory Usage
```bash
free -h
```

### Check Running Processes
```bash
ps aux | grep gunicorn
ps aux | grep celery
```

### Check Network Connections
```bash
sudo netstat -tuln | grep :80
sudo netstat -tuln | grep :443
sudo ss -tuln
```

### Run Health Check
```bash
cd /var/www/pos/backend
./deployment/health_check.sh
```

## Troubleshooting

### Service Won't Start
```bash
# Check detailed logs
sudo journalctl -u posbackend -n 100 --no-pager

# Check if port is in use
sudo lsof -i :8000

# Check socket file
ls -la /var/www/pos/backend/gunicorn.sock
sudo rm /var/www/pos/backend/gunicorn.sock  # Remove if corrupted
sudo systemctl restart posbackend
```

### 502 Bad Gateway
```bash
# Usually means Gunicorn isn't running
sudo systemctl status posbackend
sudo systemctl restart posbackend
tail -f /var/www/pos/backend/logs/gunicorn_error.log
```

### Static Files Not Loading
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=.env.production
python manage.py collectstatic --clear --noinput
sudo systemctl restart posbackend
```

### Database Connection Failed
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
sudo -u postgres psql -d pos_production -U pos_user

# Check .env.production credentials
cat /var/www/pos/backend/.env.production | grep DB_
```

### Clear All Logs
```bash
cd /var/www/pos/backend/logs
truncate -s 0 *.log
```

## Git Operations (on server)

### Check Current Branch
```bash
cd /var/www/pos/backend
git branch
git status
```

### Pull Latest Changes
```bash
git pull origin main
```

### View Recent Commits
```bash
git log --oneline -10
```

### Discard Local Changes
```bash
git reset --hard origin/main
```

## Redis Operations

### Access Redis CLI
```bash
redis-cli
```

### Check Redis Status
```bash
sudo systemctl status redis
redis-cli ping
```

### Clear Redis Cache
```bash
redis-cli FLUSHALL
```

## Performance Monitoring

### Check Response Time
```bash
curl -o /dev/null -s -w "Time: %{time_total}s\n" http://your-domain.com
```

### Monitor Real-time Requests
```bash
sudo tail -f /var/log/nginx/posbackend_access.log
```

### Count Requests
```bash
# Requests in last hour
sudo grep "$(date -d '1 hour ago' +'%d/%b/%Y:%H')" /var/log/nginx/posbackend_access.log | wc -l
```

## Emergency Recovery

### Rollback Deployment
```bash
cd /var/www/pos/backend
git log --oneline -10  # Find the commit to rollback to
git checkout <commit-hash>
./deployment/deploy.sh
```

### Restart All Services
```bash
sudo systemctl restart posbackend posbackend-celery posbackend-celery-beat nginx redis postgresql
```

### Kill Stuck Processes
```bash
# Find processes
ps aux | grep gunicorn
ps aux | grep celery

# Kill specific process
sudo kill -9 <PID>

# Or restart service
sudo systemctl restart posbackend
```

---

## Useful Aliases

Add these to your `~/.bashrc` for quicker access:

```bash
alias pos='cd /var/www/pos/backend'
alias posenv='source /var/www/pos/backend/venv/bin/activate'
alias poslogs='tail -f /var/www/pos/backend/logs/gunicorn_error.log'
alias posrestart='sudo systemctl restart posbackend posbackend-celery posbackend-celery-beat && sudo systemctl reload nginx'
alias posstatus='sudo systemctl status posbackend posbackend-celery posbackend-celery-beat nginx --no-pager'
alias posdeploy='cd /var/www/pos/backend && ./deployment/deploy.sh'
alias poshealth='cd /var/www/pos/backend && ./deployment/health_check.sh'
```

Then run:
```bash
source ~/.bashrc
```
