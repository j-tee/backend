# 🧪 Quick Test: Verify Backend Returns Numbers

**Purpose:** Verify the backend fix is working and returns numbers (not strings)

---

## ⚡ Quick Shell Test

```bash
cd /home/teejay/Documents/Projects/pos/backend

venv/bin/python manage.py shell -c "
from sales.models import Sale
from sales.serializers import SaleSerializer
from rest_framework.renderers import JSONRenderer
import json

# Get any completed sale
sale = Sale.objects.filter(status='COMPLETED').first()

if sale:
    # Serialize and render as JSON
    serializer = SaleSerializer(sale)
    renderer = JSONRenderer()
    json_data = renderer.render(serializer.data)
    data = json.loads(json_data)
    
    # Check types
    print('✅ VERIFICATION RESULTS:')
    print('')
    
    # Sale amounts
    total = data['total_amount']
    print(f'total_amount: {total}')
    print(f'  Type in JSON: number ✅' if isinstance(total, (int, float)) else f'  Type in JSON: string ❌')
    
    # Line item amounts
    if data['line_items']:
        item = data['line_items'][0]
        qty = item['quantity']
        print(f'')
        print(f'quantity: {qty}')
        print(f'  Type in JSON: number ✅' if isinstance(qty, (int, float)) else f'  Type in JSON: string ❌')
        
        # Test math
        price = item['unit_price']
        total = qty * price
        print(f'')
        print(f'Math test: {qty} * {price} = {total:.2f} ✅')
        print('')
        print('✅ ALL CHECKS PASSED - Backend returns numbers!')
    else:
        print('❌ No line items found')
else:
    print('❌ No sales found')
"
```

---

## 🌐 Quick API Test

```bash
# Get auth token first
TOKEN="your-token-here"

# Test the API endpoint
curl -s -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/sales/api/sales/?status=COMPLETED&limit=1" \
  | python3 -m json.tool | head -50

# Look for:
# "quantity": 13.0        ✅ Number (no quotes)
# NOT "quantity": "13.00" ❌ String (has quotes)
```

---

## 📋 Expected Output

### ✅ CORRECT (Numbers)

```json
{
  "total_amount": 3166.25,
  "line_items": [
    {
      "quantity": 13.0,
      "unit_price": 243.56,
      "total_price": 3166.25
    }
  ]
}
```

### ❌ WRONG (Strings)

```json
{
  "total_amount": "3166.25",
  "line_items": [
    {
      "quantity": "13.00",
      "unit_price": "243.56",
      "total_price": "3166.25"
    }
  ]
}
```

---

## 🔍 What to Check

1. **No quotes around numbers** in JSON
2. **Python shell shows** `(int, float)` not `str`
3. **Math operations work** without parseFloat
4. **Frontend .toFixed()** doesn't throw TypeError

---

## ✅ Success Criteria

- [ ] `total_amount` is a number
- [ ] `quantity` is a number
- [ ] `unit_price` is a number
- [ ] `cost_price` is a number (or null)
- [ ] Math operations work: `qty * price`
- [ ] No `TypeError` in frontend console

---

**If all checks pass:** ✅ Backend fix is working!  
**If any fail:** ❌ Check `sales/serializers.py` for `coerce_to_string=False`
