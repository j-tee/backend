# Quick Reference - Tests & Scripts

## 🧪 Running Tests

```bash
# All tests
python manage.py test tests

# Specific file
python manage.py test tests.test_sales_export

# With coverage
coverage run --source='.' manage.py test tests
coverage report
```

## 🔧 Common Scripts

```bash
# Setup test data
python scripts/populate_quick_data.py

# Create test user
python scripts/create_test_user.py

# Verify data
python scripts/verify_reconciliation.py

# Check inventory
python scripts/check_inventory.py
```

## 📁 Directory Structure

```
backend/
├── tests/          # All test files (32)
│   ├── README.md   # Test documentation
│   └── test_*.py
│
├── scripts/        # All utility scripts (17)
│   ├── README.md   # Script documentation
│   └── *.py
│
└── manage.py       # Django management
```

## 📖 Documentation

- **Test Guide:** `tests/README.md`
- **Script Guide:** `scripts/README.md`
- **Full Summary:** `ORGANIZATION_SUMMARY.md`

## ✅ What Changed

- ✅ 32 test files → `tests/`
- ✅ 17 script files → `scripts/`
- ✅ Root directory 98% cleaner
- ✅ 2 comprehensive READMEs added

## 🎯 Benefits

- Cleaner project structure
- Easy to find tests/scripts
- Better IDE support
- Professional organization
