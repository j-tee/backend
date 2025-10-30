# SSL/HTTPS Setup Guide

Complete guide to enable SSL/HTTPS for your POS Backend API.

## Prerequisites

- ✅ Nginx configured and serving HTTP on port 80
- ✅ Domain DNS records pointing to server (posbackend.alphalogiquetechnologies.com → 68.66.251.79)
- ✅ Domain accessible via HTTP first
- ✅ Port 80 and 443 open in firewall

## Quick Setup (Automated)

### Step 1: Ensure HTTP is Working First

Before setting up SSL, verify your site is accessible via HTTP:

```bash
curl http://posbackend.alphalogiquetechnologies.com
```

You should see the landing page HTML.

### Step 2: Run the SSL Setup Script

```bash
ssh deploy@68.66.251.79 -p 7822
cd /var/www/pos/backend
./deployment/setup_ssl.sh
```

The script will:
1. Install certbot (if not already installed)
2. Verify domain accessibility
3. Obtain SSL certificate from Let's Encrypt
4. Update nginx configuration for HTTPS
5. Enable HTTP to HTTPS redirect
6. Configure auto-renewal

### Step 3: Update Django Settings

Add SSL settings to your `.env.production` file:

```bash
nano /var/www/pos/backend/.env.production
```

Add these lines:

```bash
# SSL/HTTPS Settings
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

### Step 4: Restart Gunicorn

```bash
sudo systemctl restart gunicorn
```

### Step 5: Test HTTPS

```bash
curl https://posbackend.alphalogiquetechnologies.com
```

## Manual Setup (Alternative)

If you prefer manual setup or the script fails:

### Install Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### Obtain Certificate

**Method 1: Webroot (Preferred)**

```bash
sudo certbot certonly --webroot \
  -w /var/www/pos/backend/staticfiles \
  -d posbackend.alphalogiquetechnologies.com \
  --email admin@alphalogiquetechnologies.com \
  --agree-tos \
  --non-interactive
```

**Method 2: Standalone (if webroot fails)**

```bash
# Stop nginx temporarily
sudo /opt/nginx/sbin/nginx -s stop

# Get certificate
sudo certbot certonly --standalone \
  -d posbackend.alphalogiquetechnologies.com \
  --email admin@alphalogiquetechnologies.com \
  --agree-tos \
  --non-interactive

# Start nginx
sudo /opt/nginx/sbin/nginx
```

### Update Nginx Configuration

Replace `/opt/nginx/conf/conf.d/pos_backend.conf` with:

```nginx
upstream pos_backend {
    server unix:/var/www/pos/backend/gunicorn.sock fail_timeout=0;
}

# HTTP - Redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name posbackend.alphalogiquetechnologies.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name posbackend.alphalogiquetechnologies.com;
    
    # SSL Certificates
    ssl_certificate /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/privkey.pem;
    
    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/chain.pem;
    
    charset utf-8;
    client_max_body_size 75M;
    
    access_log /var/www/pos/backend/logs/nginx_access.log;
    error_log /var/www/pos/backend/logs/nginx_error.log;
    
    location /static/ {
        alias /var/www/pos/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /var/www/pos/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    location / {
        proxy_pass http://pos_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location ~ /\. {
        deny all;
    }
}
```

### Test and Reload

```bash
sudo /opt/nginx/sbin/nginx -t
sudo /opt/nginx/sbin/nginx -s reload
```

## Certificate Auto-Renewal

Certbot automatically configures renewal via systemd timer.

### Check Auto-Renewal Status

```bash
sudo systemctl status certbot.timer
```

### Test Renewal

```bash
sudo certbot renew --dry-run
```

### Manual Renewal (if needed)

```bash
sudo certbot renew
sudo /opt/nginx/sbin/nginx -s reload
```

## Verification

### Check SSL Certificate

```bash
sudo certbot certificates
```

### Test SSL Configuration

```bash
# Using curl
curl -I https://posbackend.alphalogiquetechnologies.com

# Using openssl
openssl s_client -connect posbackend.alphalogiquetechnologies.com:443 -servername posbackend.alphalogiquetechnologies.com
```

### Online SSL Test

Visit: https://www.ssllabs.com/ssltest/analyze.html?d=posbackend.alphalogiquetechnologies.com

You should get an A or A+ rating.

## Troubleshooting

### Certificate Validation Failed

**Issue:** Let's Encrypt can't verify domain ownership

**Solutions:**
1. Ensure domain points to server: `dig posbackend.alphalogiquetechnologies.com`
2. Check firewall: `sudo ufw status` (ports 80 and 443 must be open)
3. Verify nginx is serving HTTP: `curl http://posbackend.alphalogiquetechnologies.com`

### Certificate Files Not Found

**Issue:** Nginx can't find SSL certificate files

**Check:**
```bash
ls -la /etc/letsencrypt/live/posbackend.alphalogiquetechnologies.com/
```

Files should include:
- `fullchain.pem`
- `privkey.pem`
- `chain.pem`

### Mixed Content Warnings

**Issue:** Browser shows "not fully secure" warning

**Solution:**
Ensure all resources (CSS, JS, images) use HTTPS or relative URLs.

### Django Redirect Loop

**Issue:** Infinite redirect when accessing site

**Solution:**
Check `.env.production` has:
```bash
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

And nginx config includes:
```nginx
proxy_set_header X-Forwarded-Proto $scheme;
```

## Security Best Practices

### HSTS Preloading

After 3+ months of stable HTTPS, submit to HSTS preload list:
https://hstspreload.org/

### Certificate Monitoring

Set up monitoring alerts for:
- Certificate expiration (30 days before)
- Auto-renewal failures
- SSL configuration changes

### Regular Updates

```bash
# Update certbot
sudo apt update && sudo apt upgrade certbot

# Check for nginx security updates
sudo apt list --upgradable | grep nginx
```

## URLs After SSL Setup

Your API will be available at:

- ✅ `https://posbackend.alphalogiquetechnologies.com/` - Landing page
- ✅ `https://posbackend.alphalogiquetechnologies.com/admin/` - Django admin
- ✅ `https://posbackend.alphalogiquetechnologies.com/api/docs/` - API docs
- ✅ All HTTP requests automatically redirect to HTTPS

## Certificate Information

- **Issuer:** Let's Encrypt
- **Validity:** 90 days
- **Auto-renewal:** ~60 days (automatic via certbot timer)
- **Type:** Domain Validation (DV)
- **Cost:** Free

## Summary

After SSL setup:
1. ✅ All traffic encrypted with TLS 1.2/1.3
2. ✅ Automatic HTTP to HTTPS redirect
3. ✅ A+ SSL rating with modern security
4. ✅ Auto-renewal configured
5. ✅ HSTS enabled for added security
6. ✅ Django configured for HTTPS

Your POS Backend API is now production-ready with enterprise-grade security! 🔒🚀
