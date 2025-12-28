# Automatic Service File Deployment

## Overview

The GitHub Actions workflow now **automatically copies and updates systemd service files** during deployment. No manual intervention needed!

---

## What Happens on Every Deployment

When you push to `main`, the GitHub Actions workflow automatically:

1. ✅ **Copies service files** from `deployment/` to `/etc/systemd/system/`
2. ✅ **Reloads systemd** to recognize changes
3. ✅ **Enables services** for auto-start on boot
4. ✅ **Restarts services** with updated configuration

---

## Service Files Managed Automatically

| Source File | Destination | Service Name |
|-------------|-------------|--------------|
| `deployment/gunicorn.service` | `/etc/systemd/system/posbackend.service` | Django/Gunicorn |
| `deployment/celery.service` | `/etc/systemd/system/posbackend-celery.service` | Celery Worker |
| `deployment/celery-beat.service` | `/etc/systemd/system/posbackend-celery-beat.service` | Celery Beat Scheduler |

---

## Workflow Process

```yaml
# In .github/workflows/deploy.yml

# 1. Update service files
sudo cp -f deployment/gunicorn.service /etc/systemd/system/posbackend.service
sudo cp -f deployment/celery.service /etc/systemd/system/posbackend-celery.service
sudo cp -f deployment/celery-beat.service /etc/systemd/system/posbackend-celery-beat.service

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable auto-start
sudo systemctl enable posbackend
sudo systemctl enable posbackend-celery
sudo systemctl enable posbackend-celery-beat

# 4. Restart services
sudo systemctl restart posbackend
sudo systemctl restart posbackend-celery
sudo systemctl restart posbackend-celery-beat
```

---

## One-Time Setup Required

### Step 1: Update Sudoers Configuration

**On your VPS (as root or sudo user):**

```bash
# SSH into your VPS
ssh root@your-vps-ip  # or ssh your-sudo-user@your-vps-ip

# Navigate to project directory
cd /var/www/pos/backend

# Pull latest code (to get updated sudoers script)
git pull origin main

# Run the sudoers update script
sudo bash deployment/update_sudoers.sh
```

**What this does:**
- Grants `deploy` user passwordless sudo access for:
  - Service management (`systemctl restart`, `enable`, `status`)
  - Service file copying (`cp -f deployment/*.service /etc/systemd/system/`)
  - Systemd reload (`systemctl daemon-reload`)
  - Nginx management

### Step 2: Verify Permissions

```bash
# Switch to deploy user
su - deploy

# Test service file copying (dry run)
sudo cp -f /var/www/pos/backend/deployment/celery.service /etc/systemd/system/posbackend-celery.service

# Test systemd commands
sudo systemctl daemon-reload
sudo systemctl status posbackend-celery

# If no password prompt appears, you're good! ✅
```

---

## How to Update Service Files

### Developer Workflow

1. **Edit service file locally:**
   ```bash
   # Example: Update Celery concurrency
   nano deployment/celery.service
   
   # Change:
   ExecStart=... --concurrency=2
   # To:
   ExecStart=... --concurrency=4
   ```

2. **Commit and push:**
   ```bash
   git add deployment/celery.service
   git commit -m "feat: Increase Celery worker concurrency to 4"
   git push origin development
   ```

3. **Merge to main:**
   ```bash
   # Create PR or merge directly
   git checkout main
   git merge development
   git push origin main
   ```

4. **Automatic deployment triggers:**
   - GitHub Actions detects push to `main`
   - Runs tests
   - **Automatically copies updated service file**
   - Reloads systemd
   - Restarts service with new configuration
   - ✅ Done! No manual SSH needed

---

## Example Scenarios

### Scenario 1: Increase Celery Workers

**File:** `deployment/celery.service`

```diff
ExecStart=/var/www/pos/backend/venv/bin/celery -A app worker \
-          --concurrency=2 \
+          --concurrency=4 \
          --loglevel=info
```

**Action:**
```bash
git add deployment/celery.service
git commit -m "perf: Increase Celery worker concurrency to 4"
git push origin main
```

**Result:** Service automatically updated on VPS within ~2 minutes

---

### Scenario 2: Add Celery Task Time Limits

**File:** `deployment/celery.service`

```diff
ExecStart=/var/www/pos/backend/venv/bin/celery -A app worker \
          --concurrency=2 \
+          --time-limit=300 \
+          --soft-time-limit=270 \
          --loglevel=info
```

**Action:** Commit → Push → Auto-deploy ✅

---

### Scenario 3: Change Celery Beat Schedule

**File:** `app/celery.py`

```python
beat_schedule={
    'new-task': {
        'task': 'inventory.tasks.send_stock_report',
        'schedule': 3600.0,  # Every hour
    },
}
```

**Action:**
```bash
git commit -am "feat: Add hourly stock report task"
git push origin main
```

**Result:**
- Code updated
- Celery Beat service restarted
- New schedule active ✅

---

## Troubleshooting

### Problem: "Permission denied" during deployment

**Solution:**
```bash
# SSH into VPS
ssh root@your-vps-ip

# Re-run sudoers setup
cd /var/www/pos/backend
sudo bash deployment/update_sudoers.sh

# Verify
su - deploy
sudo systemctl daemon-reload  # Should work without password
```

---

### Problem: Service file not updating

**Check deployment logs:**
```
1. Go to: https://github.com/j-tee/backend/actions
2. Click latest workflow run
3. Check "Deploy to VPS" step
4. Look for "Updating systemd service files" section
```

**Manual verification on VPS:**
```bash
ssh deploy@your-vps-ip

# Check if file was copied
ls -l /etc/systemd/system/posbackend-celery.service

# Compare with source
diff /etc/systemd/system/posbackend-celery.service \
     /var/www/pos/backend/deployment/celery.service

# If different, manually copy
sudo cp -f /var/www/pos/backend/deployment/celery.service \
           /etc/systemd/system/posbackend-celery.service
sudo systemctl daemon-reload
sudo systemctl restart posbackend-celery
```

---

### Problem: Service won't restart

**Check service status:**
```bash
ssh deploy@your-vps-ip
sudo systemctl status posbackend-celery --no-pager
sudo journalctl -u posbackend-celery -n 50
```

**Common issues:**
- ❌ Virtual environment not activated
- ❌ Dependencies not installed
- ❌ Incorrect file paths in service file
- ❌ Redis not running

---

## Security Considerations

### Sudoers Configuration is Restrictive

The `/etc/sudoers.d/deploy` file **only** allows:

✅ **Allowed:**
- Copying service files from `/var/www/pos/backend/deployment/` only
- Running `systemctl` commands on `posbackend*` services only
- Reloading nginx configuration

❌ **Not Allowed:**
- Running arbitrary commands as root
- Copying files to other locations
- Managing other services
- Shell access as root

### Why This is Safe

1. **Specific paths:** Only allows copying from project's `deployment/` folder
2. **Specific services:** Only manages `posbackend*` services
3. **No shell access:** Cannot run `sudo bash` or arbitrary commands
4. **Validated by visudo:** Syntax errors prevented by validation script

---

## Monitoring Automatic Deployments

### View Real-Time Deployment

**GitHub Actions UI:**
```
1. Go to: https://github.com/j-tee/backend/actions
2. Click on running workflow
3. Click "deploy" job
4. Watch "Deploy to VPS" step in real-time
```

**Expected output:**
```
=== Updating systemd service files ===
'/var/www/pos/backend/deployment/gunicorn.service' -> '/etc/systemd/system/posbackend.service'
'/var/www/pos/backend/deployment/celery.service' -> '/etc/systemd/system/posbackend-celery.service'
'/var/www/pos/backend/deployment/celery-beat.service' -> '/etc/systemd/system/posbackend-celery-beat.service'
✓ Service files updated

Restarting services...
✓ posbackend restarted
✓ posbackend-celery restarted
✓ posbackend-celery-beat restarted
```

---

## Benefits

### Before (Manual Process)

```bash
# Edit service file locally
nano deployment/celery.service

# Commit
git commit -am "Update celery workers"
git push

# SSH into VPS
ssh deploy@vps

# Manually copy
sudo cp deployment/celery.service /etc/systemd/system/posbackend-celery.service

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart posbackend-celery

# Total time: ~5 minutes
# Error-prone: might forget steps
```

### After (Automatic Process)

```bash
# Edit service file locally
nano deployment/celery.service

# Commit and push
git commit -am "Update celery workers"
git push origin main

# That's it! ✅
# Total time: ~2 minutes (automated)
# Error-free: consistent process
```

---

## Summary

✅ **Automatic Service Deployment Enabled**

**When you push to `main`:**
1. Service files automatically copied to `/etc/systemd/system/`
2. Systemd automatically reloaded
3. Services automatically restarted with new config
4. No manual SSH required

**One-time setup:**
```bash
# On VPS as root
sudo bash /var/www/pos/backend/deployment/update_sudoers.sh
```

**Done!** 🎉 All future service file updates deploy automatically!
