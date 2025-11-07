# 🚀 AI Features Quick Start Guide

**For:** Developers deploying the AI-powered POS backend  
**Time Required:** 15 minutes  
**Date:** November 7, 2025

---

## ✅ Prerequisites

- [x] OpenAI API key configured in environment
- [x] Django backend running
- [x] PostgreSQL database configured
- [x] Redis installed (optional, for caching)

---

## 📦 Step 1: Install Dependencies (2 minutes)

```bash
cd /home/teejay/Documents/Projects/pos/backend

# Activate virtual environment
source .venv/bin/activate

# Install AI packages
pip install openai==1.54.0 tiktoken==0.7.0 python-dateutil==2.9.0

# Or install all requirements
pip install -r requirements.txt
```

---

## ⚙️ Step 2: Configure Environment (1 minute)

Add to your `.env.production` or `.env.development`:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-98zDBEfjbjiQvfH6wobivS6QNyPS...
OPENAI_ORGANIZATION=  # Optional
AI_FEATURES_ENABLED=True
```

**Get Your OpenAI Key:**
1. Go to: https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-proj-`)
4. Add to environment file

---

## 🗄️ Step 3: Run Database Migrations (1 minute)

```bash
# Create AI feature tables
python manage.py migrate ai_features

# You should see:
# Running migrations:
#   Applying ai_features.0001_initial... OK
```

**Tables Created:**
- `business_ai_credits` - Credit balances
- `ai_transactions` - Transaction log
- `ai_credit_purchases` - Purchase history
- `ai_usage_alerts` - Low credit alerts

---

## 🧪 Step 4: Test the Installation (5 minutes)

### 4a. Start the Server

```bash
python manage.py runserver
```

### 4b. Test Credit Balance Endpoint

```bash
# Get your auth token (from login or Django admin)
export TOKEN="your-auth-token-here"

# Test credit balance
curl -H "Authorization: Token $TOKEN" \
  http://localhost:8000/ai/api/credits/balance/
```

**Expected Response:**
```json
{
  "balance": 0.00,
  "message": "No active AI credits. Purchase credits to get started."
}
```

### 4c. Grant Test Credits (Django Shell)

```bash
python manage.py shell
```

```python
from ai_features.services import AIBillingService
from decimal import Decimal
from accounts.models import Business

# Get your business
business = Business.objects.first()  # Or filter by name/id

# Grant 10 free credits for testing
result = AIBillingService.purchase_credits(
    business_id=str(business.id),
    amount_paid=Decimal('0.00'),
    credits_purchased=Decimal('10.00'),
    payment_reference='TEST-FREE-CREDITS',
    payment_method='free_trial'
)

print(f"Credits added: {result['credits_added']}")
print(f"New balance: {result['new_balance']}")

exit()
```

### 4d. Test Natural Language Query

```bash
# Test query endpoint
curl -X POST \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my total sales this month?"}' \
  http://localhost:8000/ai/api/query/
```

**Expected Response:**
```json
{
  "answer": "Based on your sales data, you made...",
  "query_type": "sales",
  "data": {...},
  "follow_up_questions": [...],
  "credits_used": 0.50,
  "new_balance": 9.50
}
```

✅ **If you get this response, everything is working!**

---

## 📊 Step 5: Access Django Admin (2 minutes)

```bash
# Create superuser if needed
python manage.py createsuperuser

# Start server
python manage.py runserver
```

**Visit:** http://localhost:8000/admin/

**You should see:**
- Business AI Credits
- AI Transactions
- AI Credit Purchases
- AI Usage Alerts

**Try:**
1. Click "Business AI Credits" → See credit balances
2. Click "AI Transactions" → See transaction history
3. Grant manual credits to businesses

---

## 🎨 Step 6: Frontend Integration (5 minutes)

### Example: Add Query Box to Dashboard

```jsx
import React, { useState } from 'react';

const QuickAIQuery = () => {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  const handleQuery = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/ai/api/query/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query })
      });
      
      const data = await response.json();
      setAnswer(data.answer);
    } catch (error) {
      alert('Query failed: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h3>🤖 Ask About Your Business</h3>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g., 'What were my sales today?'"
        style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
      />
      <button 
        onClick={handleQuery} 
        disabled={loading}
        style={{ padding: '10px 20px' }}
      >
        {loading ? 'Thinking...' : 'Ask (0.5 credits)'}
      </button>
      {answer && (
        <div style={{ marginTop: '15px', whiteSpace: 'pre-wrap' }}>
          <strong>Answer:</strong>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );
};

export default QuickAIQuery;
```

**Add to your dashboard and test!**

---

## 🎯 Example Queries to Test

Try these questions:

**Sales:**
- "What were my total sales this month?"
- "How many sales did I make today?"
- "Show me sales for last week"

**Products:**
- "Which product is my top seller?"
- "How many Samsung TVs were sold in January?"
- "Show me my slowest-moving products"

**Customers:**
- "Who are my top 10 customers?"
- "Show me customers who haven't purchased in 30 days"
- "How many new customers this month?"

**Inventory:**
- "What products are out of stock?"
- "Show me low stock items"
- "What's my total inventory value?"

**Financial:**
- "What's my profit this month?"
- "Show me revenue by category"
- "What's my average transaction value?"

---

## 🔍 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'openai'"

**Solution:**
```bash
source .venv/bin/activate
pip install openai==1.54.0 tiktoken==0.7.0 python-dateutil==2.9.0
```

### Problem: "OPENAI_API_KEY not configured"

**Solution:**
```bash
# Check environment file
cat .env.production | grep OPENAI

# Add if missing
echo "OPENAI_API_KEY=sk-proj-your-key" >> .env.production
```

### Problem: "insufficient_credits"

**Solution:**
```bash
# Grant test credits via Django shell (see Step 4c)
```

### Problem: "OpenAI API Error: Authentication failed"

**Solution:**
- Check API key is valid
- Visit: https://platform.openai.com/api-keys
- Generate new key if needed

### Problem: Migrations fail

**Solution:**
```bash
# Check if tables already exist
python manage.py migrate --fake ai_features

# Or drop tables and recreate
python manage.py migrate ai_features zero
python manage.py migrate ai_features
```

---

## 📚 Next Steps

1. **Read Full Documentation:**
   - `docs/AI_FRONTEND_API_DOCUMENTATION.md` - Complete API reference
   - `docs/AI_IMPLEMENTATION_COMPLETE.md` - Implementation summary

2. **Implement Frontend:**
   - Add credit balance widget
   - Add query interface
   - Add credit purchase flow

3. **Test All Features:**
   - Natural language queries ✅
   - Product descriptions ✅
   - Collection messages ✅
   - Credit assessments ✅

4. **Production Deployment:**
   - Set production OpenAI key
   - Configure payment gateway (Paystack)
   - Set up monitoring
   - Enable rate limiting

---

## ✅ Quick Verification Checklist

- [ ] Dependencies installed (`pip list | grep openai`)
- [ ] Environment configured (`OPENAI_API_KEY` set)
- [ ] Migrations run (`python manage.py showmigrations ai_features`)
- [ ] Server starts without errors
- [ ] Credit balance endpoint works
- [ ] Test credits granted
- [ ] Natural language query works
- [ ] Django admin shows AI models
- [ ] Frontend can connect to endpoints

**If all checked, you're ready to go! 🎉**

---

## 🚀 Production Deployment Tips

### 1. Set Production API Key
```env
OPENAI_API_KEY=sk-proj-production-key
```

### 2. Enable Caching (Redis)
```python
# settings.py already configured
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### 3. Monitor Costs
```bash
# Check monthly usage
curl -H "Authorization: Token $TOKEN" \
  "https://your-domain.com/ai/api/usage/stats/?days=30"
```

### 4. Set Budget Caps (settings.py)
```python
AI_BUDGET_CAPS = {
    'per_business_daily': Decimal('10.0'),
    'per_business_monthly': Decimal('200.0'),
    'platform_monthly': Decimal('10000.0'),
}
```

---

## 💡 Pro Tips

1. **Cache Aggressively:** Product descriptions don't change often - cache for 30 days
2. **Batch Requests:** Use collection priority endpoint instead of individual assessments
3. **Monitor Tokens:** Track `tokens_used` in transactions to optimize prompts
4. **Free Credits:** Give new users 5-10 free credits to try features
5. **Upsell:** Show "Try AI features" when users view reports/customers
6. **Highlight Savings:** Show time saved (e.g., "Saved 2 hours on collections")

---

## 🎓 Learn More

**OpenAI Documentation:**
- API Reference: https://platform.openai.com/docs/api-reference
- Best Practices: https://platform.openai.com/docs/guides/production-best-practices
- Pricing: https://openai.com/pricing

**Django Documentation:**
- Models: https://docs.djangoproject.com/en/5.2/topics/db/models/
- REST Framework: https://www.django-rest-framework.org/

**Project Documentation:**
- See `/docs/` folder for all AI documentation
- Check README files in each app

---

## 📞 Get Help

**Issues?**
- Check Django logs: `logs/django.log`
- Check OpenAI status: https://status.openai.com
- Review error responses in API calls

**Questions?**
- Read `AI_FRONTEND_API_DOCUMENTATION.md`
- Check implementation guide
- Review code comments

---

**🎉 You're all set! Happy coding!** 🚀

**Time to Complete:** ~15 minutes  
**Status:** Ready for production! ✅  
**Next:** Build amazing AI-powered features! 💡

---

**P.S.** The system can now answer questions like:
> "How many Samsung TVs were sold between January and March?"

And get intelligent, natural language answers with insights! 🎯
