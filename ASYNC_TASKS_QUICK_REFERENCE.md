# Quick Reference: Using Async Tasks in Views

## How to Call Async Tasks from Django Views

### Pattern 1: Fire and Forget (No Result Needed)

```python
from accounts.tasks import send_welcome_email

@api_view(['POST'])
def register_user(request):
    user = User.objects.create(...)
    
    # Send email in background (no waiting)
    send_welcome_email.delay(user.id)
    
    return Response({'status': 'created'})
```

**Use when:** User doesn't need to know when task completes

---

### Pattern 2: Return Task ID for Polling

```python
from reports.tasks import generate_sales_report

@api_view(['POST'])
def request_sales_report(request):
    business = request.business
    start_date = request.data['start_date']
    end_date = request.data['end_date']
    
    # Queue report generation
    task = generate_sales_report.delay(
        str(business.id),
        start_date,
        end_date,
        format='pdf'
    )
    
    # Return task ID immediately
    return Response({
        'task_id': task.id,
        'status': 'processing',
        'message': 'Report generation started'
    }, status=202)  # 202 Accepted
```

**Frontend polls for completion:**
```python
@api_view(['GET'])
def check_report_status(request, task_id):
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id)
    
    if task.state == 'SUCCESS':
        result = task.result  # {'file_url': '...', 'status': 'completed'}
        return Response({
            'status': 'completed',
            'file_url': result['file_url']
        })
    elif task.state == 'PENDING':
        return Response({'status': 'processing'})
    elif task.state == 'FAILURE':
        return Response({
            'status': 'failed',
            'error': str(task.info)
        }, status=500)
```

**Use when:** User needs to download result file

---

### Pattern 3: Webhook Processing (Idempotent)

```python
from ai_features.tasks import process_payment_webhook

@api_view(['POST'])
def payment_webhook(request):
    # Validate webhook signature first
    if not validate_signature(request):
        return Response({'error': 'Invalid'}, status=400)
    
    reference = request.data['reference']
    amount = request.data['amount']
    
    # Queue async processing (fast response)
    process_payment_webhook.delay(
        payment_reference=reference,
        amount_paid=str(amount),
        payment_provider='paystack'
    )
    
    # Return immediately (webhook won't timeout)
    return Response({'status': 'queued'})
```

**Use when:** External webhooks require fast response (<1s)

---

### Pattern 4: Scheduled Background Tasks (No View Needed)

```python
# Configured in app/celery.py beat_schedule
'send-low-stock-alerts': {
    'task': 'inventory.tasks.send_low_stock_alert',
    'schedule': 21600.0,  # Every 6 hours
}
```

**Runs automatically**, no view invocation needed.

---

## Task State Flow

```
PENDING → STARTED → SUCCESS
                 ↘ RETRY → SUCCESS
                         ↘ FAILURE
```

---

## Common Task Signatures

### Reports
```python
from reports.tasks import (
    generate_sales_report,
    generate_inventory_report,
    export_customers_to_csv,
    export_transactions_to_excel
)

# Sales Report (PDF, Excel, CSV)
generate_sales_report.delay(business_id, start_date, end_date, format='pdf')

# Inventory Report
generate_inventory_report.delay(business_id, format='excel', include_zero_stock=False)

# Customer Export
export_customers_to_csv.delay(business_id)

# Transaction Export
export_transactions_to_excel.delay(business_id, start_date, end_date)
```

### Notifications
```python
from inventory.tasks import (
    send_low_stock_alert,
    send_stock_movement_report,
    check_expiring_products
)

from ai_features.tasks import send_low_credit_alert

# Low Stock Alert
send_low_stock_alert.delay(business_id, product_ids=None)

# Stock Movement Report
send_stock_movement_report.delay(business_id, period_days=7)

# Expiring Products
check_expiring_products.delay(business_id, days_threshold=30)

# Low AI Credits
send_low_credit_alert.delay(business_id, current_balance, threshold=10.0)
```

### Payments
```python
from ai_features.tasks import (
    process_payment_webhook,
    send_credit_purchase_notification
)

# Process Webhook
process_payment_webhook.delay(payment_reference, amount_paid, payment_provider)

# Send Notification
send_credit_purchase_notification.delay(purchase_id)
```

---

## Error Handling Best Practices

### 1. Catch Specific Exceptions

```python
from reports.tasks import generate_sales_report
from celery.exceptions import TaskError

try:
    task = generate_sales_report.delay(business_id, start, end)
    return Response({'task_id': task.id})
except TaskError as e:
    # Celery-specific error
    return Response({'error': 'Task queue unavailable'}, status=503)
```

### 2. Validate Before Queuing

```python
# Bad - queues task even if business doesn't exist
generate_sales_report.delay('invalid-id', start, end)

# Good - validate first
try:
    business = Business.objects.get(id=business_id)
except Business.DoesNotExist:
    return Response({'error': 'Business not found'}, status=404)

# Now queue task
generate_sales_report.delay(str(business.id), start, end)
```

### 3. Set Timeouts

```python
from celery.exceptions import TimeoutError

task = generate_sales_report.delay(business_id, start, end)

try:
    result = task.get(timeout=10)  # Wait max 10 seconds
except TimeoutError:
    # Task still running
    return Response({'status': 'processing', 'task_id': task.id})
```

---

## When to Use Async vs Sync

### Use Async Tasks For:
✅ Sending emails  
✅ Generating reports  
✅ Processing webhooks  
✅ Heavy data exports  
✅ External API calls  
✅ Batch operations  
✅ Scheduled jobs  

### Keep Synchronous For:
❌ Simple CRUD operations  
❌ Database queries  
❌ User authentication  
❌ Session management  
❌ Cache reads/writes  
❌ Simple calculations  

---

## Performance Tips

### 1. Don't Pass Large Objects

```python
# Bad - serializes entire queryset
products = Product.objects.all()
process_products.delay(products)  # Will fail or be slow

# Good - pass IDs only
product_ids = list(Product.objects.values_list('id', flat=True))
process_products.delay(product_ids)
```

### 2. Use Chunking for Large Datasets

```python
from celery import group

# Process 1000 products in batches of 100
product_ids = list(range(1, 1001))
chunks = [product_ids[i:i+100] for i in range(0, len(product_ids), 100)]

# Execute in parallel
job = group(process_batch.delay(chunk) for chunk in chunks)
result = job.apply_async()
```

### 3. Set Task Time Limits

```python
@shared_task(time_limit=300)  # 5 minutes max
def generate_large_report(business_id):
    # Will be killed if takes longer than 5 minutes
    pass
```

---

## Debugging Tasks

### View Active Tasks
```bash
celery -A app inspect active
```

### View Registered Tasks
```bash
celery -A app inspect registered
```

### Purge Queue (Clear all pending tasks)
```bash
celery -A app purge
```

### Test Task in Shell
```python
python manage.py shell

from reports.tasks import generate_sales_report

# Run synchronously (blocking)
result = generate_sales_report('123', '2025-01-01', '2025-12-31')
print(result)

# Run async
task = generate_sales_report.delay('123', '2025-01-01', '2025-12-31')
print(task.state)
```

---

## Common Patterns in Frontend

### React Polling Pattern

```javascript
// 1. Trigger async task
const response = await fetch('/api/reports/sales/', {
  method: 'POST',
  body: JSON.stringify({ start_date: '2025-01-01', end_date: '2025-12-31' })
});

const { task_id } = await response.json();

// 2. Poll for completion
const checkStatus = async () => {
  const res = await fetch(`/api/tasks/${task_id}/status/`);
  const data = await res.json();
  
  if (data.status === 'completed') {
    // Download file
    window.location.href = data.file_url;
  } else if (data.status === 'processing') {
    // Check again in 2 seconds
    setTimeout(checkStatus, 2000);
  } else {
    // Failed
    alert('Report generation failed');
  }
};

checkStatus();
```

---

## Summary

**Key Takeaways:**
1. Use `.delay()` to queue tasks asynchronously
2. Return task IDs for user-facing operations that need results
3. Validate inputs before queuing (save worker resources)
4. Handle task states: PENDING, SUCCESS, FAILURE
5. Use polling pattern in frontend for long-running tasks
6. Keep webhook endpoints fast (<100ms) with async processing

**When in doubt:** If operation takes >1 second, make it async!
