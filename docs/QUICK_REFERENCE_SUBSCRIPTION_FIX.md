# Quick Reference: Subscription Flow Fix

## 📋 TLDR

**Problem:** Users can choose cheaper plans than they should pay for  
**Solution:** Remove plan selection, auto-detect storefronts, auto-calculate price  
**Impact:** Prevents revenue loss, fixes security hole  
**Timeline:** 3 weeks to implement  

---

## 🎯 Core Issue

```
❌ WRONG: User selects plan → System charges selected price
✅ RIGHT: System detects storefronts → Auto-calculates price → User subscribes
```

---

## 📄 Documents Created

| Document | Purpose | Audience |
|----------|---------|----------|
| `CRITICAL_SUBSCRIPTION_FLOW_ISSUE.md` | Full problem analysis, business impact | Everyone |
| `FRONTEND_BACKEND_SUBSCRIPTION_API_CONTRACT.md` | Technical specification, implementation guide | Developers |
| `EMAIL_TEMPLATES_SUBSCRIPTION_ISSUE.md` | Communication templates | Team Leads |
| `QUICK_REFERENCE_SUBSCRIPTION_FIX.md` | This document | Everyone |

---

## 🔄 What Changed

### Before (Broken)
```
User → Sees plans → Selects plan → Pays plan price
```

### After (Fixed)
```
User → System detects storefronts → Shows calculated price → User subscribes
```

---

## 🔌 New API Endpoint

```bash
GET /api/subscriptions/my-pricing/
Authorization: Bearer {token}

Response:
{
  "storefront_count": 4,
  "base_price": "200.00",
  "total_amount": "218.00",
  "currency": "GHS"
}
```

---

## 💻 Frontend Changes Required

### Remove
- ❌ Plan selection dropdown
- ❌ Plan cards/buttons
- ❌ Calls to `/pricing/calculate/?storefronts=X`
- ❌ Any code that sends `plan_id`

### Add
- ✅ Call to `/api/subscriptions/my-pricing/`
- ✅ Display auto-calculated price
- ✅ Simple "Subscribe Now" button
- ✅ Storefront count display

---

## 🔨 Backend Changes Required

### Implement
- ✅ `GET /api/subscriptions/my-pricing/` endpoint
- ✅ Auto-detect storefront count
- ✅ Server-side price calculation
- ✅ Validation to prevent price manipulation

---

## 📊 Pricing Tiers (Reference)

| Storefronts | Base Price | Total (with tax) |
|-------------|------------|------------------|
| 1 | GHS 100 | GHS 109 |
| 2 | GHS 150 | GHS 163.50 |
| 3 | GHS 175 | GHS 190.75 |
| 4 | GHS 200 | GHS 218 |
| 5+ | GHS 250 + GHS 50/extra | Calculated |

Tax Rate: 9% (VAT 3% + NHIL 2.5% + GETFund 2.5% + COVID-19 1%)

---

## ⚠️ Security Concerns

**Current Vulnerability:**
- User with 4 storefronts can select 2-storefront plan
- Revenue loss: GHS 54.50/month per user
- No validation prevents this

**Fix:**
- Backend ignores any plan selection
- Backend counts ACTUAL storefronts
- Backend calculates correct price
- Frontend cannot manipulate pricing

---

## 🧪 Test Scenarios

1. **User with 1 storefront** → Should see GHS 109
2. **User with 2 storefronts** → Should see GHS 163.50
3. **User with 4 storefronts** → Should see GHS 218
4. **User with 0 storefronts** → Should see error
5. **User adds storefront** → Price should update

---

## 📅 Timeline

| Week | Backend | Frontend |
|------|---------|----------|
| 1 | Implement endpoint, validation | Remove plan UI, call new endpoint |
| 2 | Testing, bug fixes | Implement new UI, testing |
| 3 | Deploy | Deploy |
| 4 | Data audit | Monitor |

---

## ✅ Checklist

### Before Meeting
- [ ] Read `CRITICAL_SUBSCRIPTION_FLOW_ISSUE.md`
- [ ] Read `FRONTEND_BACKEND_SUBSCRIPTION_API_CONTRACT.md`
- [ ] Review current subscription code
- [ ] List questions and concerns

### During Meeting
- [ ] Understand the problem
- [ ] Agree on solution
- [ ] Commit to timeline
- [ ] Accept assignments

### After Meeting
- [ ] Complete assigned tasks
- [ ] Test thoroughly
- [ ] Update documentation
- [ ] Deploy

---

## 🚀 Quick Implementation Steps

### Backend
```bash
# 1. Add endpoint
# In subscriptions/views.py
@action(detail=False, methods=['get'])
def my_pricing(self, request):
    # Auto-detect storefronts
    # Calculate price
    # Return pricing breakdown

# 2. Add validation
# In create() method
def create(self, request):
    # Ignore any plan_id from request
    # Calculate based on actual storefronts
    # Create subscription
```

### Frontend
```typescript
// 1. Fetch pricing
const pricing = await fetch('/api/subscriptions/my-pricing/');

// 2. Display
<div>
  <p>Storefronts: {pricing.storefront_count}</p>
  <p>Total: {pricing.currency} {pricing.total_amount}</p>
  <button onClick={subscribe}>Subscribe Now</button>
</div>

// 3. Subscribe (no plan selection)
await fetch('/api/subscriptions/', {
  method: 'POST',
  body: JSON.stringify({})  // Empty!
});
```

---

## 📞 Contacts

**Questions?** Post in #subscription-redesign Slack channel  
**Backend Issues:** Tag @backend-team  
**Frontend Issues:** Tag @frontend-team  
**Product Questions:** Tag @product-owner  

---

## 🔗 Related Links

- Backend Repo: [Link]
- Frontend Repo: [Link]
- API Documentation: [Link]
- Figma Designs: [Link]
- Project Board: [Link]

---

## ⚡ Emergency Contacts

If this breaks in production:
1. Check backend logs: `tail -f /var/log/gunicorn/error.log`
2. Check frontend console errors
3. Verify API endpoint is accessible
4. Check database pricing tiers exist
5. Contact: [Emergency contact]

---

## 💡 Key Takeaways

1. **No more plan selection** - System decides based on storefronts
2. **Server-side pricing** - Frontend cannot manipulate
3. **Automatic detection** - Less user confusion
4. **Security first** - Prevent revenue leakage
5. **Better UX** - Simpler, clearer flow

---

## 📈 Success Metrics

After deployment, we should see:
- ✅ Zero price manipulation incidents
- ✅ Correct billing for all new subscriptions
- ✅ Improved user experience (fewer support tickets)
- ✅ Revenue protection

---

## 🎓 Lessons Learned

1. **Communicate early** about business logic
2. **Document assumptions** before implementation
3. **Validate across teams** before deploying
4. **Security review** for payment flows
5. **Test edge cases** thoroughly

---

**Last Updated:** November 3, 2025  
**Status:** Ready for Implementation  
**Priority:** HIGH - CRITICAL  

---

**Quick Start:**
1. Read this document (5 min)
2. Read full spec if you're implementing (30 min)
3. Attend alignment meeting (1.5 hours)
4. Start coding!

---

**END OF QUICK REFERENCE**
