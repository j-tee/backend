# Deployment Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEVELOPER MACHINE                            │
│                                                                       │
│  ┌──────────────┐                                                    │
│  │   VS Code    │                                                    │
│  │              │                                                    │
│  │  git commit  │                                                    │
│  │  git push    │────────┐                                          │
│  └──────────────┘        │                                          │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          GITHUB                                      │
│                                                                       │
│  ┌──────────────────────┐         ┌─────────────────────┐           │
│  │   Your Repository    │         │  GitHub Actions     │           │
│  │                      │────────▶│                     │           │
│  │   - Code             │         │  1. Run Tests       │           │
│  │   - .github/         │         │  2. If pass, deploy │           │
│  │   - deployment/      │         │  3. SSH to VPS      │           │
│  └──────────────────────┘         └─────────┬───────────┘           │
│                                              │                       │
└──────────────────────────────────────────────┼───────────────────────┘
                                               │ SSH (port 7822)
                                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VPS (68.66.251.79)                                │
│                                                                       │
│  ┌────────────────────────────────────────────────────────┐          │
│  │                  NGINX (Port 80/443)                   │          │
│  │                  Web Server / Reverse Proxy            │          │
│  │  - Serves static files                                 │          │
│  │  - Proxies requests to Gunicorn                        │          │
│  │  - Handles SSL/HTTPS                                   │          │
│  └─────────────────────┬──────────────────────────────────┘          │
│                        │                                             │
│                        ▼                                             │
│  ┌────────────────────────────────────────────────────────┐          │
│  │            GUNICORN (Unix Socket)                      │          │
│  │            WSGI Application Server                     │          │
│  │  - Runs Django application                             │          │
│  │  - Multiple workers (3)                                │          │
│  │  - Managed by systemd (posbackend.service)             │          │
│  └─────────────────────┬──────────────────────────────────┘          │
│                        │                                             │
│                        ▼                                             │
│  ┌────────────────────────────────────────────────────────┐          │
│  │              DJANGO APPLICATION                        │          │
│  │           /var/www/pos/backend/                        │          │
│  │                                                         │          │
│  │  - Business logic                                      │          │
│  │  - API endpoints                                       │          │
│  │  - Models & database queries                           │          │
│  │  - Static files (CSS, JS)                              │          │
│  │  - Media files (uploads)                               │          │
│  └────┬───────────────────────────┬────────────┬──────────┘          │
│       │                           │            │                     │
│       ▼                           ▼            ▼                     │
│  ┌─────────┐              ┌─────────────┐  ┌──────────┐             │
│  │PostgreSQL│              │   Redis     │  │  Celery  │             │
│  │Database  │              │   Cache     │  │  Worker  │             │
│  │          │              │             │  │          │             │
│  │Port 5432 │              │  Port 6379  │  │Background│             │
│  │          │              │             │  │  Tasks   │             │
│  │- Stores  │              │- Cache data │  │          │             │
│  │  all data│              │- Session    │  │Managed by│             │
│  │- Users   │              │- Celery     │  │systemd   │             │
│  │- Products│              │  broker     │  │          │             │
│  │- Sales   │              │             │  │          │             │
│  └─────────┘              └─────────────┘  └────┬─────┘             │
│                                                  │                   │
│                                                  ▼                   │
│                                            ┌──────────┐              │
│                                            │Celery    │              │
│                                            │Beat      │              │
│                                            │          │              │
│                                            │Periodic  │              │
│                                            │Tasks     │              │
│                                            │Scheduler │              │
│                                            └──────────┘              │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. User Request Flow
```
User Browser
    │
    ▼
NGINX (Port 80/443)
    │
    ├──▶ /static/  ──▶ Serve static files directly
    │
    ├──▶ /media/   ──▶ Serve media files directly
    │
    └──▶ /api/     ──▶ Proxy to Gunicorn
                        │
                        ▼
                   Gunicorn Worker
                        │
                        ▼
                   Django Application
                        │
                        ├──▶ Read/Write ──▶ PostgreSQL
                        │
                        ├──▶ Cache ──▶ Redis
                        │
                        └──▶ Queue Task ──▶ Celery
                                            │
                                            ▼
                                    Background Processing
```

### 2. Deployment Flow
```
Developer
    │
    ├──▶ git commit
    │
    └──▶ git push origin main
            │
            ▼
        GitHub Repository
            │
            ▼
        GitHub Actions
            │
            ├──▶ Checkout code
            │
            ├──▶ Run tests (PostgreSQL + Redis)
            │
            └──▶ If tests pass ──▶ SSH to VPS
                                    │
                                    ▼
                            VPS (/var/www/pos/backend)
                                    │
                                    ├──▶ git pull origin main
                                    │
                                    ├──▶ pip install -r requirements.txt
                                    │
                                    ├──▶ python manage.py migrate
                                    │
                                    ├──▶ python manage.py collectstatic
                                    │
                                    └──▶ systemctl restart services
                                            │
                                            ├──▶ posbackend (Gunicorn)
                                            │
                                            ├──▶ posbackend-celery
                                            │
                                            ├──▶ posbackend-celery-beat
                                            │
                                            └──▶ nginx reload
```

## File Structure on VPS

```
/var/www/pos/backend/
│
├── .env.production           # Production environment variables
├── .git/                     # Git repository
├── venv/                     # Python virtual environment
│
├── app/                      # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                 # User accounts app
├── inventory/                # Inventory management
├── sales/                    # Sales management
├── reports/                  # Reports
├── settings/                 # System settings
├── subscriptions/            # Subscription management
│
├── staticfiles/              # Collected static files (CSS, JS, images)
│   └── (automatically generated)
│
├── media/                    # User uploaded files
│   └── (user uploads)
│
├── logs/                     # Application logs
│   ├── gunicorn_access.log
│   ├── gunicorn_error.log
│   ├── celery_worker.log
│   └── celery_beat.log
│
├── deployment/               # Deployment scripts
│   ├── initial_setup.sh
│   ├── deploy.sh
│   ├── ssl_setup.sh
│   ├── health_check.sh
│   └── *.service files
│
├── gunicorn.sock            # Unix socket for Gunicorn
├── manage.py                # Django management script
└── requirements.txt         # Python dependencies
```

## System Services

### Systemd Services
```
/etc/systemd/system/
│
├── posbackend.service           # Main Django application (Gunicorn)
│   └── Runs on: Unix socket at /var/www/pos/backend/gunicorn.sock
│
├── posbackend-celery.service    # Celery worker
│   └── Processes: Background tasks
│
└── posbackend-celery-beat.service  # Celery beat
    └── Processes: Scheduled periodic tasks
```

### Nginx Configuration
```
/etc/nginx/
│
├── sites-available/
│   └── posbackend              # Your configuration
│
└── sites-enabled/
    └── posbackend → ../sites-available/posbackend  (symlink)
```

## Port Usage

| Service | Port | Access |
|---------|------|--------|
| HTTP | 80 | Public (via NGINX) |
| HTTPS | 443 | Public (via NGINX, after SSL setup) |
| SSH | 7822 | Admin only |
| PostgreSQL | 5432 | Localhost only |
| Redis | 6379 | Localhost only |
| Gunicorn | Unix socket | Internal (via NGINX) |

## Security Layers

```
Internet
    │
    ▼
Firewall (UFW)
    │ (Allow: 80, 443, 7822)
    │
    ▼
NGINX
    │ (Reverse proxy, SSL termination)
    │
    ▼
Gunicorn
    │ (Application server, Unix socket)
    │
    ▼
Django
    │ (Authentication, permissions, RBAC)
    │
    ▼
PostgreSQL
    (Data layer, user isolation)
```

## Monitoring Points

1. **NGINX Access Logs**: `/var/log/nginx/posbackend_access.log`
2. **NGINX Error Logs**: `/var/log/nginx/posbackend_error.log`
3. **Gunicorn Logs**: `/var/www/pos/backend/logs/gunicorn_*.log`
4. **Django Logs**: `/var/www/pos/backend/logs/django.log`
5. **Celery Logs**: `/var/www/pos/backend/logs/celery_*.log`
6. **System Logs**: `sudo journalctl -u posbackend`

## Backup Strategy

```
Daily Automated Backups
    │
    ├──▶ Database Backup
    │       └── pg_dump → /var/www/pos/backend/backups/
    │
    ├──▶ Media Files
    │       └── rsync → backup location
    │
    └──▶ Configuration
            └── .env.production, nginx.conf → backup location

Retention: 7 days
```

## Scaling Considerations

### Current Setup (Single Server)
- 3 Gunicorn workers
- 1 Celery worker
- 1 Redis instance
- 1 PostgreSQL instance

### Future Scaling Options

1. **Horizontal Scaling**
   - Multiple application servers behind a load balancer
   - Separate database server
   - Redis cluster for caching

2. **Vertical Scaling**
   - Increase Gunicorn workers: `(2 × CPU cores) + 1`
   - Add more Celery workers
   - Upgrade server resources

3. **Database Optimization**
   - Connection pooling (pgBouncer)
   - Read replicas
   - Query optimization

## Disaster Recovery

### Quick Recovery Steps

1. **Application Failure**
   ```bash
   sudo systemctl restart posbackend
   ./deployment/health_check.sh
   ```

2. **Database Corruption**
   ```bash
   # Restore from latest backup
   psql -U pos_user pos_production < backup_YYYYMMDD.sql
   sudo systemctl restart posbackend
   ```

3. **Full Server Failure**
   - Provision new VPS
   - Run `initial_setup.sh`
   - Restore database from backup
   - Restore media files
   - Update DNS (if changed IP)

## Performance Monitoring

### Key Metrics to Monitor

1. **Response Time**: NGINX access logs
2. **Error Rate**: Application error logs
3. **Database Performance**: PostgreSQL slow query log
4. **Memory Usage**: `free -h`
5. **Disk Usage**: `df -h`
6. **CPU Usage**: `top` or `htop`
7. **Active Connections**: `netstat -an`

---

**This architecture provides:**
✅ High availability
✅ Easy maintenance
✅ Scalability
✅ Security
✅ Monitoring capabilities
✅ Disaster recovery
