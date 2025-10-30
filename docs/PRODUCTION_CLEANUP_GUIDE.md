# Production Cleanup Guide: Fix Corrupted Storefront Inventory

## Overview
This guide walks you through fixing the corrupted storefront inventory caused by the transaction rollback bug.

## Prerequisites
- SSH access to production server
- Backup of production database (recommended)
- The bug fix has been deployed to production

## Step 1: Backup the Database (CRITICAL)

```bash
# SSH into production
ssh deploy@pos.alphalogiquetechnologies.com -p 7822

# Navigate to project directory
cd /var/www/pos/backend

# Create backup
source venv/bin/activate
python manage.py dumpdata inventory.StoreFrontInventory > backup_storefront_inventory_$(date +%Y%m%d_%H%M%S).json

# Or full database backup (recommended)
pg_dump -h localhost -U your_db_user your_db_name > backup_full_$(date +%Y%m%d_%H%M%S).sql
```

## Step 2: Run Dry-Run First (See What Would Change)

```bash
# For specific product (10mm Metal Cable)
python manage.py fix_storefront_inventory --product-name "10mm Metal Cable" --dry-run --verbose

# Expected output:
# *** DRY RUN MODE - No changes will be made ***
# 
# ======================================================================
# Product: 10mm Metal Cable (SKU: ...)
# ID: ...
# 
# Warehouse stock intake: 10 units
# Fulfilled transfer requests: X units
# 
# Storefront: [Name]
#   Current quantity: 284
#   Correct quantity: X
#   Discrepancy: XXX units (overcapacity)
#   → Would change to: X units
```

## Step 3: Verify the Numbers

Before running the actual fix, verify:

1. **Warehouse stock intake** = Total units received in warehouse
2. **Fulfilled transfers** = Sum of FULFILLED transfer requests only
3. **Correct quantity** should be ≤ warehouse stock intake

If fulfilled transfers > warehouse intake, you have additional data issues to investigate.

## Step 4: Run the Actual Fix

### Option A: Fix Specific Product (Safest)

```bash
# Using product name
python manage.py fix_storefront_inventory --product-name "10mm Metal Cable" --verbose

# Or using product ID
python manage.py fix_storefront_inventory --product-id "your-uuid-here" --verbose
```

### Option B: Fix All Products (Use with caution)

```bash
# First, dry-run on all products
python manage.py fix_storefront_inventory --all --dry-run

# If results look good, run actual fix
python manage.py fix_storefront_inventory --all --verbose
```

## Step 5: Verify the Fix

```bash
# Check the specific product again
python manage.py shell -c "
from inventory.models import Product, StoreFrontInventory, StockProduct
from django.db.models import Sum

product = Product.objects.filter(name__icontains='10mm Metal Cable').first()

if product:
    # Warehouse stock
    warehouse = StockProduct.objects.filter(product=product).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    # Storefront inventory
    storefront = StoreFrontInventory.objects.filter(product=product).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    print(f'Product: {product.name}')
    print(f'Warehouse stock: {warehouse}')
    print(f'Storefront inventory: {storefront}')
    print(f'Status: {"✓ OK" if storefront <= warehouse else "✗ ISSUE"}')
"
```

## Step 6: Quick Command Reference

### From Local Machine (One-liner)

```bash
# Dry-run for 10mm Metal Cable
ssh deploy@pos.alphalogiquetechnologies.com -p 7822 "cd /var/www/pos/backend && export \$(grep -v '^#' .env.production | grep -v '^$' | xargs) && source venv/bin/activate && python manage.py fix_storefront_inventory --product-name '10mm Metal Cable' --dry-run --verbose"

# Actual fix for 10mm Metal Cable
ssh deploy@pos.alphalogiquetechnologies.com -p 7822 "cd /var/www/pos/backend && export \$(grep -v '^#' .env.production | grep -v '^$' | xargs) && source venv/bin/activate && python manage.py fix_storefront_inventory --product-name '10mm Metal Cable' --verbose"

# Verify the fix
ssh deploy@pos.alphalogiquetechnologies.com -p 7822 "cd /var/www/pos/backend && export \$(grep -v '^#' .env.production | grep -v '^$' | xargs) && source venv/bin/activate && python manage.py shell -c \"
from inventory.models import Product, StoreFrontInventory, StockProduct
from django.db.models import Sum

product = Product.objects.filter(name__icontains='10mm Metal Cable').first()
if product:
    warehouse = StockProduct.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
    storefront = StoreFrontInventory.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
    print(f'Warehouse: {warehouse}, Storefront: {storefront}, Status: {\\\"OK\\\" if storefront <= warehouse else \\\"ISSUE\\\"}')
\""
```

## Step 7: Monitor After Fix

```bash
# Check for any new discrepancies (should be none after bug fix deployed)
python manage.py shell -c "
from inventory.models import Product, StoreFrontInventory, StockProduct
from django.db.models import Sum

products = Product.objects.filter(storefront_inventory_entries__isnull=False).distinct()

issues = []
for product in products:
    warehouse = StockProduct.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
    storefront = StoreFrontInventory.objects.filter(product=product).aggregate(total=Sum('quantity'))['total'] or 0
    
    if storefront > warehouse:
        issues.append({
            'product': product.name,
            'warehouse': warehouse,
            'storefront': storefront,
            'excess': storefront - warehouse
        })

if issues:
    print('Products with overcapacity:')
    for issue in issues:
        print(f'  {issue[\"product\"]}: warehouse={issue[\"warehouse\"]}, storefront={issue[\"storefront\"]} (excess: {issue[\"excess\"]})')
else:
    print('✓ No overcapacity issues found')
"
```

## Rollback Plan (If Something Goes Wrong)

```bash
# Restore from JSON backup
python manage.py loaddata backup_storefront_inventory_20251030_HHMMSS.json

# Or restore from full database backup
psql -h localhost -U your_db_user your_db_name < backup_full_20251030_HHMMSS.sql
```

## Expected Results

For "10mm Metal Cable":
- **Before fix**: Storefront = 284 units, Warehouse = 10 units (274 units overcapacity)
- **After fix**: Storefront = correct value based on FULFILLED transfers only
- **Validation**: Storefront quantity ≤ Warehouse quantity

## Troubleshooting

### Issue: "Fulfilled transfers exceed warehouse stock"

This means the data corruption goes deeper than just the transaction bug. Investigate:
1. Check if there are duplicate FULFILLED transfer requests
2. Verify warehouse stock intake records are correct
3. Look for manual database modifications

### Issue: "No changes made but discrepancy still exists"

Ensure:
1. The bug fix has been deployed to production
2. You're running the latest version of the management command
3. The database connection is to production, not a local copy

### Issue: "Command not found"

```bash
# Make sure the management command file exists
ls -la inventory/management/commands/fix_storefront_inventory.py

# If missing, upload it:
scp -P 7822 inventory/management/commands/fix_storefront_inventory.py \
    deploy@pos.alphalogiquetechnologies.com:/var/www/pos/backend/inventory/management/commands/

# Then restart the application
sudo systemctl restart gunicorn
```

## Post-Cleanup Checklist

- [ ] Backup created successfully
- [ ] Dry-run completed and reviewed
- [ ] Actual fix executed successfully
- [ ] Verification shows correct quantities
- [ ] No new overcapacity issues appearing
- [ ] Bug fix deployed to prevent recurrence
- [ ] Users notified of temporary inventory discrepancies (if needed)

## Support

If you encounter issues not covered here, check:
1. Django logs: `/var/www/pos/backend/logs/`
2. Database integrity: Run `python manage.py check --database default`
3. Transfer request audit trail: Check `TransferRequest` and `TransferRequestLineItem` records
