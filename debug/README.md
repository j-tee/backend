# Debug & Test Scripts

This folder contains debugging, testing, and verification scripts used during development.

## 🧪 Test Scripts

### API & Integration Tests
- **`test_endpoint_access.py`** - Test API endpoint access and permissions
- **`test_integration.py`** - Integration tests for the system
- **`test_rbac_api.py`** - RBAC (Role-Based Access Control) API tests
- **`test_sales_view.py`** - Sales view functionality tests
- **`test_catalog_filtering_manual.sh`** - Manual catalog filtering tests

### Verification Scripts
- **`verify_sales_quantities.py`** - Verify sales quantities integrity
- **`debug_user_business.py`** - Debug user-business relationships

## 📄 Test Output Files

### Receipts (`receipts/`)
- Sample receipt HTML files generated during testing
- Used for receipt template verification

### Logs
- **`population_output.log`** - Database population script output

## 🚀 Usage

### Running Test Scripts

```bash
# Python test scripts
python debug/test_endpoint_access.py
python debug/test_integration.py
python debug/test_rbac_api.py
python debug/test_sales_view.py

# Shell test scripts
bash debug/test_catalog_filtering_manual.sh

# Verification scripts
python debug/verify_sales_quantities.py
python debug/debug_user_business.py
```

### Running Django Tests

For proper Django unit tests, use:
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test inventory
python manage.py test sales

# Run specific test file
python manage.py test accounts.tests.test_models

# Run with verbosity
python manage.py test --verbosity=2

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

## 📝 Notes

- These scripts are for development/debugging only
- Not included in production deployments
- Some scripts may require test data to be populated
- Check individual scripts for specific usage instructions

## ⚠️ Important

- Do not run these scripts on production databases
- Some scripts may modify data
- Always backup before running verification/debug scripts
- Use test environments for integration tests

## 🔗 Related

- **Production Scripts**: See [`../scripts/`](../scripts/) for production utility scripts
- **Unit Tests**: See `tests/` folders in each app
- **Documentation**: See [`../docs/`](../docs/) for feature documentation

---

**These are development tools - use with caution!**
