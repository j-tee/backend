# Nginx Server Block Setup Guide

This guide will help you configure nginx to serve your POS Backend API.

## Prerequisites

- ✅ Repository cloned at `/var/www/pos/backend`
- ✅ Gunicorn service running and listening on Unix socket
- ✅ Nginx installed at `/opt/nginx/`
- ✅ Deploy user has sudo access

## Quick Setup (Automated)

### Option 1: Using the Setup Script

1. **SSH into your server:**
   ```bash
   ssh deploy@68.66.251.79 -p 7822
   ```

2. **Navigate to the backend directory:**
   ```bash
   cd /var/www/pos/backend
   ```

3. **Run the setup script:**
   ```bash
   ./deployment/setup_nginx.sh
   ```

4. **Follow the prompts:**
   - Enter your domain name (e.g., `api.yourcompany.com`)
   - Confirm nginx reload

That's it! The script will:
- Copy the nginx configuration
- Update the domain name
- Test the configuration
- Reload nginx

## Manual Setup (Step by Step)

### Step 1: Copy the Configuration

```bash
sudo cp /var/www/pos/backend/deployment/pos_backend.conf /opt/nginx/conf/conf.d/pos_backend.conf
```

### Step 2: Edit the Configuration

```bash
sudo nano /opt/nginx/conf/conf.d/pos_backend.conf
```

Update the `server_name` directive:
```nginx
server_name your-actual-domain.com;  # Replace with your domain
```

**Domain Options:**
- Use your domain: `api.yourcompany.com`
- Use server IP: `68.66.251.79`
- Use multiple: `api.yourcompany.com www.api.yourcompany.com`

### Step 3: Test the Configuration

```bash
sudo /opt/nginx/sbin/nginx -t
```

You should see:
```
nginx: configuration file /opt/nginx/conf/nginx.conf test is successful
```

### Step 4: Reload Nginx

```bash
sudo /opt/nginx/sbin/nginx -s reload
```

### Step 5: Verify Services

```bash
# Check Gunicorn is running
sudo systemctl status gunicorn

# Check if socket file exists
ls -la /var/www/pos/backend/gunicorn.sock

# Test nginx is serving
curl -I http://localhost
```

## Configuration Details

### What the Config Does

1. **Upstream Block:**
   - Points to Gunicorn Unix socket at `/var/www/pos/backend/gunicorn.sock`
   - Provides failover handling

2. **Static Files:**
   - Serves from `/var/www/pos/backend/staticfiles/`
   - 30-day cache for performance

3. **Media Files:**
   - Serves from `/var/www/pos/backend/media/`
   - 7-day cache

4. **Proxy Settings:**
   - Forwards requests to Gunicorn
   - Preserves original headers (Host, IP, etc.)
   - Supports WebSockets

5. **Security Headers:**
   - Prevents clickjacking
   - Blocks MIME-type sniffing
   - XSS protection

### Ports

- **HTTP**: Port 80 (configured)
- **HTTPS**: Port 443 (add SSL config later)

## Testing

### 1. Test from Server (Local)

```bash
curl http://localhost
```

You should see the beautiful landing page HTML.

### 2. Test from External

```bash
curl http://your-domain.com
# or
curl http://68.66.251.79
```

### 3. Test Specific Endpoints

```bash
# Landing page
curl http://your-domain.com/

# Admin
curl http://your-domain.com/admin/

# API docs
curl http://your-domain.com/api/docs/

# API endpoints
curl http://your-domain.com/inventory/api/products/
```

## Troubleshooting

### Issue: 502 Bad Gateway

**Cause:** Gunicorn not running or socket not accessible

**Solution:**
```bash
# Check Gunicorn status
sudo systemctl status gunicorn

# Restart Gunicorn
sudo systemctl restart gunicorn

# Check socket permissions
ls -la /var/www/pos/backend/gunicorn.sock

# Check Gunicorn logs
sudo journalctl -u gunicorn -n 50
```

### Issue: 404 Not Found

**Cause:** Wrong path or static files not collected

**Solution:**
```bash
cd /var/www/pos/backend
source venv/bin/activate
export DJANGO_ENV_FILE=/var/www/pos/backend/.env.production
python manage.py collectstatic --noinput
```

### Issue: Permission Denied

**Cause:** Nginx can't access socket file

**Solution:**
```bash
# Ensure nginx user can access socket
sudo usermod -a -G deploy deploy
sudo chmod 770 /var/www/pos/backend/
```

### Issue: Static Files Not Loading

**Cause:** Path incorrect or permissions

**Solution:**
```bash
# Check static files exist
ls -la /var/www/pos/backend/staticfiles/

# Fix permissions
sudo chown -R deploy:deploy /var/www/pos/backend/staticfiles/
sudo chmod -R 755 /var/www/pos/backend/staticfiles/
```

## View Logs

```bash
# Nginx access log
tail -f /var/www/pos/backend/logs/nginx_access.log

# Nginx error log
tail -f /var/www/pos/backend/logs/nginx_error.log

# Gunicorn log
tail -f /var/www/pos/backend/logs/gunicorn.log
```

## Next Steps: SSL/HTTPS Setup

After basic setup works, secure your API with SSL:

### Install Certbot

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

### Get SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will:
- Verify domain ownership
- Install SSL certificate
- Update nginx config automatically
- Set up auto-renewal

### Test Auto-Renewal

```bash
sudo certbot renew --dry-run
```

## DNS Configuration

Point your domain to the server:

**A Record:**
```
Type: A
Name: api (or @)
Value: 68.66.251.79
TTL: 3600
```

**AAAA Record (if IPv6):**
```
Type: AAAA
Name: api
Value: [Your IPv6 address]
TTL: 3600
```

Wait for DNS propagation (5-30 minutes).

## Summary

After setup, your API will be accessible at:
- `http://your-domain.com/` - Landing page
- `http://your-domain.com/admin/` - Django admin
- `http://your-domain.com/api/docs/` - API documentation
- `http://your-domain.com/inventory/api/` - Inventory endpoints
- `http://your-domain.com/sales/api/` - Sales endpoints
- etc.

All automated deployments via GitHub Actions will automatically reload nginx! 🚀
