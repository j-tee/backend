# AI Credits 500 Error - Fix and Manual Recovery Guide

**Date**: November 7, 2025  
**Status**: 🔴 CRITICAL - Users paid but credits not added  
**Impact**: HIGH - Payment successful but database not updated

---

## Problem Summary

**What's Happening**:
1. ✅ User purchases AI credits
2. ✅ Payment successfully completes on Paystack (payment confirmed via email)
3. ✅ Paystack redirects user back to frontend callback
4. ❌ Backend `/ai/api/credits/verify/` returns **500 Internal Server Error**
5. ❌ Credits NOT added to database
6. ❌ Purchase record remains in 'pending' status

**Result**: User paid money but didn't receive credits!

---

## Evidence

### From Screenshots

**Screenshot 1 - Payment Receipt**:
```
Business: ALPHALOGIQUE TECHNOLOGIES
Amount: GHS 32.70
Reference: AI-CREDIT-1762542056443-08ed01c0
Date: 7th Nov, 2025
Status: PAID ✅
```

**Screenshot 2 - Frontend Error**:
```
❌ Payment Verification Failed
Failed to verify AI credit payment. 
Please contact support with reference: AI-CREDIT-1762542056443-08ed01c0

Console shows:
- GET /ai/api/credits/verify/?reference=AI-CREDIT-1762542056443...
- HTTP/1.1 500 Internal Server Error ❌
- AxiosError: Request failed with status code 500
```

### From Backend Logs

```
INFO  19:00:56 POST /ai/api/credits/purchase/ HTTP/1.1 200  ✅ (Purchase created)
ERROR 19:01:10 GET /ai/api/credits/verify/... HTTP/1.1 500  ❌ (Verification failed)
```

---

## Root Cause Analysis

The 500 error is coming from the verify_payment endpoint. Based on similar issues, likely causes:

### Possibility 1: Type Conversion Bug (Most Likely)
```python
# Line 400 in ai_features/views.py
user_id=str(purchase.user_id)  # ❌ BUG: str(None) returns "None" string

# When purchase.user_id is None:
str(None) = "None"  # String "None", not NoneType None
# This causes UUID validation error when trying to save
```

### Possibility 2: PaystackException
- Network error calling Paystack
- Invalid API keys
- Reference not found

### Possibility 3: Database/Permission Error
- Credit balance record doesn't exist
- Permission denied
- Foreign key constraint

---

## Immediate Solution: Manual Credit Processing

### Step 1: List Pending Payments

```bash
cd /home/teejay/Documents/Projects/pos/backend
python3 manual_credit_processor.py --list
```

**Expected Output**:
```
Found 1 pending payment(s):

1. AI-CREDIT-1762542056443-08ed01c0
   Created: 2025-11-07 19:00:56
   Amount: GHS 32.70
   Credits: 30
```

### Step 2: Process the Pending Payment

```bash
python3 manual_credit_processor.py AI-CREDIT-1762542056443-08ed01c0
```

**Expected Output**:
```
Step 1: Fetching purchase record...
✅ Found purchase record
   Business ID: xxx
   Credits: 30
   Bonus: 0
   Status: pending

Step 2: Verifying with Paystack...
✅ Paystack verification successful
   Status: success
   Amount: GHS 32.70

Step 3: Adding credits to account...
✅ Credits added successfully!
   Credits added: 30
   New balance: 30

Step 4: Updating purchase status...
✅ Purchase status updated to 'completed'

✅ SUCCESS! Payment processed manually
```

### Step 3: Verify in Database

```bash
# Check purchase status
python3 manage.py shell

from ai_features.models import AICreditPurchase
purchase = AICreditPurchase.objects.get(payment_reference='AI-CREDIT-1762542056443-08ed01c0')
print(f"Status: {purchase.payment_status}")  # Should be 'completed'
print(f"Completed at: {purchase.completed_at}")

# Check credit balance
from ai_features.services.billing import AIBillingService
balance = AIBillingService.get_credit_balance(str(purchase.business_id))
print(f"Balance: {balance}")  # Should show the credits
```

### Step 4: Notify User

Tell the user to:
1. Refresh their browser
2. Check their AI credits balance
3. Credits should now be visible

---

## Permanent Fix: Update verify_payment Endpoint

### Fix Option 1: Update Type Conversion (Recommended)

**File**: `ai_features/views.py` (line ~400)

**Before**:
```python
result = AIBillingService.purchase_credits(
    business_id=str(purchase.business_id),
    amount_paid=amount_paid_ghs,
    credits_purchased=purchase.credits_purchased,
    payment_reference=reference,
    payment_method=purchase.payment_method,
    user_id=str(purchase.user_id),  # ❌ BUG HERE
    bonus_credits=purchase.bonus_credits
)
```

**After**:
```python
result = AIBillingService.purchase_credits(
    business_id=str(purchase.business_id),
    amount_paid=amount_paid_ghs,
    credits_purchased=purchase.credits_purchased,
    payment_reference=reference,
    payment_method=purchase.payment_method,
    user_id=str(purchase.user_id) if purchase.user_id else None,  # ✅ FIXED
    bonus_credits=purchase.bonus_credits
)
```

### Fix Option 2: Improve Error Logging (Already Applied)

I've already added better error logging to the endpoint:

```python
except Exception as e:
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(f'Exception in verify_payment: {e}', exc_info=True)
    logger.error(f'Traceback: {traceback.format_exc()}')
    return Response(
        {'error': str(e), 'type': type(e).__name__},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
```

Now the actual error will be logged to `logs/django.log` with full traceback.

---

## Testing the Fix

### Test 1: Check Actual Error

After I improved error logging, try the verify endpoint again:

```bash
# Watch the logs
tail -f logs/django.log

# Then trigger the verify endpoint from frontend or:
curl -X GET "http://localhost:8000/ai/api/credits/verify/?reference=AI-CREDIT-test" \
  -H "Authorization: Token YOUR_TOKEN"
```

Check logs for detailed error message and traceback.

### Test 2: Debug Specific Payment

```bash
python3 debug_ai_credit_payment.py AI-CREDIT-1762542056443-08ed01c0
```

This will show exactly where the error occurs.

### Test 3: End-to-End Test

After fixing:
1. Purchase new AI credits
2. Complete payment on Paystack
3. Should redirect back and automatically add credits
4. Check database to confirm

---

## Scripts Created

### 1. `manual_credit_processor.py`
**Purpose**: Manually process pending payments  
**Usage**: 
```bash
# List pending
python3 manual_credit_processor.py --list

# Process specific payment
python3 manual_credit_processor.py AI-CREDIT-xxx
```

### 2. `debug_ai_credit_payment.py`
**Purpose**: Debug why a payment is failing  
**Usage**:
```bash
python3 debug_ai_credit_payment.py AI-CREDIT-xxx
```

---

## Recovery Checklist

For each affected user:

- [ ] Find their payment reference (from Paystack email or logs)
- [ ] Run: `python3 manual_credit_processor.py --list`
- [ ] Confirm payment is 'pending' in database
- [ ] Run: `python3 manual_credit_processor.py <reference>`
- [ ] Verify credits added: Check `BusinessAICredits` table
- [ ] Notify user credits are now available
- [ ] User refreshes and sees credits

---

## Prevention

### Immediate (Emergency Fix)

1. ✅ **Apply the type conversion fix** (line 400)
2. ✅ **Improved error logging** (already done)
3. **Restart Django server** to apply changes

### Short Term

1. **Monitor logs** for any new 500 errors
2. **Set up alerts** for failed verifications
3. **Create admin dashboard** to see pending payments

### Long Term

1. **Add retry mechanism** if verification fails
2. **Webhook backup** - Use Paystack webhook to auto-process
3. **Admin interface** to manually verify payments
4. **Better error messages** to users

---

## Communication Template

For affected users:

```
Subject: AI Credits Payment Processed

Hi [User],

We noticed your AI credits payment of GHS 32.70 (Reference: AI-CREDIT-xxx) 
completed successfully, but there was a technical issue adding the credits 
to your account.

We have now manually processed your payment and added 30 credits to your 
account.

Action needed:
1. Refresh your browser
2. Navigate to AI Features page
3. Your credit balance should now show 30 credits

We apologize for the inconvenience. The technical issue has been fixed 
to prevent this from happening again.

If you have any questions, please contact support.

Thank you for your patience!
```

---

## Monitoring

### Check for Pending Payments Daily

```bash
# Add to cron or run manually
python3 manual_credit_processor.py --list

# If any pending > 1 hour old, investigate
```

### Watch Logs for 500 Errors

```bash
# Real-time monitoring
tail -f logs/django.log | grep "500.*credits/verify"

# Daily summary
grep "500.*credits/verify" logs/django.log | wc -l
```

---

## Summary

### Current Status

- **Issue**: ✅ Identified - 500 error in verify endpoint
- **User Credits**: ⏳ Pending - Need manual processing
- **Fix Applied**: ✅ Better error logging added
- **Next Fix**: ⏳ Type conversion fix (line 400)

### Action Items

**RIGHT NOW**:
1. Run `python3 manual_credit_processor.py AI-CREDIT-1762542056443-08ed01c0`
2. Verify credits added
3. Notify user

**NEXT HOUR**:
1. Check logs with improved logging to find actual error
2. Apply fix based on actual error
3. Test with new purchase

**NEXT DAY**:
1. Monitor for any new 500 errors
2. Check for other pending payments
3. Process any found

---

## Files Modified

1. ✅ `ai_features/views.py` - Improved error logging
2. ✅ `manual_credit_processor.py` - Created manual processor
3. ✅ `debug_ai_credit_payment.py` - Created debug tool
4. ✅ `docs/AI_CREDITS_500_ERROR_FIX_AND_MANUAL_RECOVERY.md` - This doc

---

**Status**: 🔴 CRITICAL - Manual intervention required  
**Priority**: IMMEDIATE - User paid but didn't receive product  
**Next Action**: Run manual credit processor NOW

---

**Last Updated**: November 7, 2025 19:30  
**Updated By**: AI Code Analysis  
**Severity**: HIGH - Payment completed but credits not delivered
