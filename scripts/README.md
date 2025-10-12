# Scripts Directory

This directory contains utility scripts, data population scripts, and demonstration scripts for the POS Backend application.

## Script Categories

### Data Population Scripts
Scripts for populating the database with test/demo data:

- `populate_data.py` - Main data population script
- `populate_datalogique_data.py` - Datalogique-specific data
- `populate_datalogique_simple.py` - Simplified Datalogique data
- `populate_quick_data.py` - Quick test data generation
- `populate_sample_data.py` - Sample data for testing
- `populate_sample_data_v2.py` - Updated sample data version

**Usage:**
```bash
python scripts/populate_data.py
python scripts/populate_quick_data.py
```

### User Management Scripts
Scripts for managing users and test accounts:

- `create_test_user.py` - Create test user accounts

**Usage:**
```bash
python scripts/create_test_user.py
```

### Inventory & Product Scripts
Scripts for managing inventory and products:

- `create_shared_products.py` - Create shared products across storefronts
- `create_storefront_inventory.py` - Create storefront-specific inventory
- `check_inventory.py` - Check inventory status and levels

**Usage:**
```bash
python scripts/check_inventory.py
python scripts/create_shared_products.py
```

### Data Cleanup Scripts
Scripts for cleaning up or deleting data:

- `delete_all_sales.py` - Delete all sales records
- `delete_sales_data.py` - Delete specific sales data

**⚠️ Warning:** Use cleanup scripts carefully, especially in production!

**Usage:**
```bash
python scripts/delete_all_sales.py  # Use with caution!
```

### Data Integrity Scripts
Scripts for fixing and verifying data integrity:

- `fix_sample_data_integrity.py` - Fix data integrity issues
- `verify_reconciliation.py` - Verify financial reconciliation
- `verify_storefront_search.py` - Verify storefront search functionality

**Usage:**
```bash
python scripts/fix_sample_data_integrity.py
python scripts/verify_reconciliation.py
```

### Demonstration Scripts
Scripts that demonstrate specific features or calculations:

- `demo_proportional_profit.py` - Demonstrate proportional profit calculations

**Usage:**
```bash
python scripts/demo_proportional_profit.py
```

## Running Scripts

### Basic Execution
```bash
# From project root
python scripts/<script_name>.py
```

### With Django Environment
Many scripts require Django to be initialized:
```bash
# Scripts typically handle this automatically
python scripts/populate_data.py
```

### Using Django Shell
Some operations can be done in Django shell:
```bash
python manage.py shell
>>> exec(open('scripts/demo_proportional_profit.py').read())
```

## Script Development Guidelines

When creating new utility scripts:

1. **Naming Convention**: Use descriptive names with underscores
   - `create_<resource>.py` - Creation scripts
   - `delete_<resource>.py` - Deletion scripts
   - `populate_<dataset>.py` - Data population
   - `verify_<feature>.py` - Verification scripts
   - `fix_<issue>.py` - Fix/repair scripts
   - `demo_<feature>.py` - Demonstration scripts

2. **Structure**: Include proper imports and Django setup
   ```python
   import os
   import sys
   import django
   
   # Setup Django
   sys.path.append('/path/to/project')
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
   django.setup()
   
   # Your script logic here
   ```

3. **Documentation**: Add docstring explaining:
   - Purpose of the script
   - Required arguments/environment
   - Expected outcomes
   - Any warnings or cautions

4. **Error Handling**: Include proper try/except blocks

5. **Confirmation**: For destructive operations, add confirmation prompts:
   ```python
   response = input("This will delete all sales. Continue? (yes/no): ")
   if response.lower() != 'yes':
       print("Aborted.")
       sys.exit(0)
   ```

## Best Practices

### 1. Environment Awareness
```python
# Check environment before running destructive operations
from django.conf import settings

if not settings.DEBUG:
    print("This script should only run in development!")
    sys.exit(1)
```

### 2. Transaction Safety
```python
from django.db import transaction

with transaction.atomic():
    # All database operations
    # Will rollback if exception occurs
```

### 3. Progress Reporting
```python
from tqdm import tqdm

for item in tqdm(items, desc="Processing"):
    # Process item
    pass
```

### 4. Logging
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Starting data population...")
```

## Common Use Cases

### Initial Setup
```bash
# 1. Create test user
python scripts/create_test_user.py

# 2. Populate with sample data
python scripts/populate_quick_data.py

# 3. Verify data integrity
python scripts/verify_reconciliation.py
```

### Development Reset
```bash
# 1. Delete all sales
python scripts/delete_all_sales.py

# 2. Repopulate with fresh data
python scripts/populate_sample_data.py
```

### Data Verification
```bash
# Check inventory levels
python scripts/check_inventory.py

# Verify search functionality
python scripts/verify_storefront_search.py

# Check financial reconciliation
python scripts/verify_reconciliation.py
```

## Safety Notes

⚠️ **Important Warnings:**

1. **Backup First**: Always backup your database before running cleanup scripts
2. **Check Environment**: Verify you're not running in production
3. **Read Script**: Review what a script does before running it
4. **Test Small**: Test with small datasets first
5. **Version Control**: Commit your work before running major operations

## Integration with Tests

Some scripts are useful for setting up test scenarios:
```bash
# In test setUp() method, you can call scripts:
from django.core.management import call_command
call_command('populate_quick_data')
```

## Maintenance

- Keep scripts updated with model changes
- Remove obsolete scripts
- Document any new parameters or requirements
- Add version comments if scripts change significantly

## Related Documentation

- Main project README: `../README.md`
- Tests documentation: `../tests/README.md`
- Database documentation: `../docs/`
