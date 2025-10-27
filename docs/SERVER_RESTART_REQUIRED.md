# Django Server Restart Required

**Issue:** Sales creation still failing with "amount_refunded required" error  
**Cause:** Django development server is using cached/old code  
**Solution:** Restart the Django development server

---

## 🔄 How to Restart Django Server

### Option 1: If Running in Terminal
1. Find the terminal where Django is running (look for `runserver` command)
2. Press `Ctrl+C` to stop the server
3. Restart with: `python manage.py runserver 8000`

### Option 2: If Running in Docker
```bash
docker-compose restart backend
# or
docker-compose down && docker-compose up -d
```

### Option 3: If Using systemd/service
```bash
sudo systemctl restart pos-backend
```

### Option 4: Kill and Restart Manually
```bash
# Find the process
ps aux | grep runserver

# Kill it (replace XXXX with the process ID)
kill -9 XXXX

# Restart
cd /home/teejay/Documents/Projects/pos/backend
source venv/bin/activate
python manage.py runserver 8000
```

---

## ✅ Verify the Fix is Loaded

After restarting, verify with:

```bash
cd /home/teejay/Documents/Projects/pos/backend
source venv/bin/activate
python manage.py shell -c "from sales.serializers import SaleSerializer; print('Read-only fields:', SaleSerializer.Meta.read_only_fields)"
```

**Expected output:**
```
Read-only fields: ['id', 'receipt_number', 'subtotal', 'total_amount', 
'amount_due', 'amount_paid', 'amount_refunded', 'created_at', 
'updated_at', 'completed_at']
```

You should see **'amount_paid'** and **'amount_refunded'** in the list ✅

---

## 🧪 Test After Restart

1. **Refresh the frontend** (Ctrl+F5 or Cmd+Shift+R)
2. **Click "New sale"** button
3. Should work without errors! ✅

---

## 📝 What Changed

**File:** `sales/serializers.py` (Line 303-309)

```python
read_only_fields = [
    'id', 'receipt_number', 'subtotal', 'total_amount', 'amount_due',
    'amount_paid', 'amount_refunded',  # ✅ ADDED
    'created_at', 'updated_at', 'completed_at'
]
```

This change tells Django REST Framework:
- Don't require `amount_paid` from the client ✅
- Don't require `amount_refunded` from the client ✅
- Use model default values (both = 0.00) ✅

---

## ⚠️ Important Notes

### Django Auto-Reload
Django's development server (`runserver`) **usually** auto-reloads when files change, BUT:

- **Sometimes** changes to serializers/models don't trigger reload
- **Cached imports** can cause old code to be used
- **Manual restart** is the safest option

### Production Deployment
When deploying to production:
- Always restart the application server (gunicorn, uwsgi, etc.)
- Clear any application caches
- Restart worker processes (if using Celery)

---

## 🚀 Quick Restart Command

```bash
# All-in-one restart command
cd /home/teejay/Documents/Projects/pos/backend && \
pkill -f "python.*runserver" && \
sleep 2 && \
source venv/bin/activate && \
python manage.py runserver 8000 &
```

This will:
1. Kill any running Django server
2. Wait 2 seconds
3. Start a new server in the background

---

**After restarting the server, sales creation will work!** 🎉
