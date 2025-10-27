# Server Restart Instructions

## The Problem
The authorization fix has been successfully committed to the codebase, but Django's auto-reload mechanism hasn't picked up the changes. You need to **manually restart the Django development server**.

## How to Restart the Server

### Step 1: Stop the Current Server
1. Find the terminal window where the Django server is running
2. Press `Ctrl+C` to stop the server
3. Wait for the server to completely shut down

### Step 2: Restart the Server
In the same terminal (or backend directory), run:

```bash
cd /home/teejay/Documents/Projects/pos/backend
source venv/bin/activate  # If using virtual environment
python manage.py runserver
```

Or if the server is configured differently:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Step 3: Verify the Fix
After restarting, test any report endpoint in your browser or with curl:

```bash
# Test with your authentication token
curl -H "Authorization: Token YOUR_AUTH_TOKEN" \
     "http://localhost:8000/reports/api/sales/summary/"
```

**Expected Result:** 200 OK with JSON data (not 403 Forbidden)

## Alternative: Kill and Restart Process

If you can't find the terminal, you can kill the process:

```bash
# Find the Django process
ps aux | grep "manage.py runserver" | grep -v grep

# Kill the process (replace PID with actual process ID)
kill 190833  # or whatever the PID is

# Start fresh
cd /home/teejay/Documents/Projects/pos/backend
source venv/bin/activate
python manage.py runserver
```

## What Was Fixed

The `get_business_id()` method in `reports/services/report_base.py` now correctly:
- Uses `user.primary_business` property (✅ correct)
- Falls back to `user.business_memberships.filter(is_active=True).first()` (✅ correct)
- No longer checks non-existent `user.business` or `user.businesses` attributes (❌ was causing the bug)

## Troubleshooting

### If 403 errors persist after restart:
1. Clear browser cache
2. Verify you're using the correct authentication token
3. Check that the user has an active BusinessMembership:
   ```python
   python manage.py shell
   from accounts.models import User
   user = User.objects.get(email='mikedlt009@gmail.com')
   print(f"Primary Business: {user.primary_business}")
   print(f"Business ID: {user.primary_business.id if user.primary_business else 'NONE'}")
   ```

### If primary_business is None:
The user doesn't have an active business membership. You need to create one:
```python
python manage.py shell
from accounts.models import User, BusinessMembership, Business
user = User.objects.get(email='mikedlt009@gmail.com')
business = Business.objects.first()  # Or get a specific business
BusinessMembership.objects.create(
    user=user,
    business=business,
    is_active=True,
    role='OWNER'  # or 'ADMIN', 'MANAGER', etc.
)
```

## Current Server Process Info
As of last check:
- Process ID: 190833
- Running in: /home/teejay/Documents/Projects/pos/backend
- Command: python manage.py runserver

---

**IMPORTANT:** The code fix is correct and committed. You just need to restart the server for it to take effect!
