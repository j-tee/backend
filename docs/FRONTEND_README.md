# 📘 Frontend Developer - Start Here

**For Subscription Implementation:** Read **`SUBSCRIPTION_API_GUIDE.md`**

That's the ONLY document you need. It contains:
- All API endpoints with request/response examples
- Authentication details
- Complete implementation flows
- TypeScript interfaces
- Payment flows (Paystack & Stripe)
- Current limitations

**One document. Everything you need.** 🎯

---

## Quick Summary

**Authentication:**
```
Authorization: Token {your-token-here}
```
NOT `Bearer` - use `Token`!

**Key Endpoints:**
- Login: `POST /accounts/api/auth/login/`
- Get Businesses: `GET /accounts/api/businesses/`
- Get Plans: `GET /subscriptions/api/plans/`
- Get Subscription: `GET /subscriptions/api/subscriptions/me/`
- Initialize Payment: `POST /subscriptions/api/subscriptions/{id}/initialize_payment/`
- Verify Payment: `POST /subscriptions/api/subscriptions/{id}/verify_payment/`

**Important:**
1. Login returns `token` (not `access_token`)
2. No `businesses` array in login response - fetch separately
3. Use `Token` authentication, not `Bearer`
4. Subscription belongs to BUSINESS, not USER

**Read the full guide:** `SUBSCRIPTION_API_GUIDE.md`
