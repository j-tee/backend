# Delete AI Credits from Database

## ⚠️ WARNING

This will **permanently delete** all AI credit related data from the database:
- Business AI Credits (credit balances)
- AI Transactions (usage logs)
- AI Credit Purchases (purchase history including the duplicate ones)
- AI Usage Alerts (alert records)

**Make sure you have a backup before proceeding!**

---

## Method 1: Python Script (Recommended)

Use the Python script that handles Django models properly:

```bash
# Activate virtual environment first
source venv/bin/activate  # or your virtualenv path

# Run the deletion script
python delete_ai_credits.py
```

The script will:
1. Show you how many records will be deleted
2. Ask for confirmation (type `yes` to proceed)
3. Delete all records in the correct order
4. Show summary of deleted records

---

## Method 2: SQL Script (Direct Database)

If you can't use Python/Django, use the SQL script:

```bash
# Using psql
psql -U postgres -d pos_db -f delete_ai_credits.sql

# Or connect to database first
psql -U postgres -d pos_db
\i delete_ai_credits.sql
```

**Note**: The SQL script uses a transaction with BEGIN/COMMIT. If something goes wrong, you can ROLLBACK.

---

## Method 3: Django Shell (Manual)

If you prefer interactive deletion:

```bash
# Activate virtualenv and run Django shell
python manage.py shell
```

Then in the shell:

```python
from ai_features.models import BusinessAICredits, AITransaction, AICreditPurchase, AIUsageAlert

# Check counts
print(f"BusinessAICredits: {BusinessAICredits.objects.count()}")
print(f"AITransaction: {AITransaction.objects.count()}")
print(f"AICreditPurchase: {AICreditPurchase.objects.count()}")
print(f"AIUsageAlert: {AIUsageAlert.objects.count()}")

# Delete all
AIUsageAlert.objects.all().delete()
AITransaction.objects.all().delete()
AICreditPurchase.objects.all().delete()
BusinessAICredits.objects.all().delete()

print("✅ All deleted!")
```

---

## Method 4: Django Admin (Manual/Selective)

For selective deletion or if you prefer a UI:

1. Go to Django admin: `http://localhost:8000/admin/`
2. Navigate to:
   - AI Features → Business AI Credits
   - AI Features → AI Transactions
   - AI Features → AI Credit Purchases
   - AI Features → AI Usage Alerts
3. Select records and choose "Delete selected" action

---

## What Gets Deleted

### BusinessAICredits
- All business credit balances
- Current balances reset to 0

### AITransaction
- All usage logs
- Historical data of AI feature usage

### AICreditPurchase
- All purchase records
- **This includes the duplicate payment references**
- All pending, completed, and failed purchases

### AIUsageAlert
- All low credit alerts
- All alert notifications

---

## After Deletion

After deleting, users will:
- Have 0 AI credits
- Need to purchase credits again
- Start fresh with no duplicate references

The payment callback fix ensures new purchases won't have duplicate reference issues.

---

## Backup First!

Before deleting, consider backing up:

```bash
# Backup entire database
pg_dump -U postgres pos_db > backup_before_ai_credits_deletion.sql

# Or backup just AI tables
pg_dump -U postgres pos_db \
  -t business_ai_credits \
  -t ai_transactions \
  -t ai_credit_purchases \
  -t ai_usage_alerts \
  > backup_ai_credits_tables.sql
```

To restore if needed:
```bash
psql -U postgres pos_db < backup_ai_credits_tables.sql
```

---

## Files Created

- `delete_ai_credits.py` - Python script (recommended)
- `delete_ai_credits.sql` - SQL script
- `DELETE_AI_CREDITS_README.md` - This file

---

## Need Help?

- Check if virtualenv is activated: `which python`
- Check Django is installed: `python -c "import django; print(django.VERSION)"`
- Check database connection: `python manage.py dbshell`
- View current data: `python manage.py shell` then query models

---

**Created**: November 7, 2025  
**Purpose**: Clean up AI credit data including duplicate payment references
