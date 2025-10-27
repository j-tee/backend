# Tests Directory

This directory contains all test files for the POS Backend application.

## Running Tests

### Run All Tests
```bash
python manage.py test tests
```

### Run Specific Test File
```bash
python manage.py test tests.test_sales_export
```

### Run with Coverage
```bash
coverage run --source='.' manage.py test tests
coverage report
```

## Test Organization

### Sales & Transactions
- `test_sale_creation.py` - Sale creation logic and validation
- `test_sale_cancellation.py` - Sale cancellation and refund logic
- `test_sales_export.py` - Sales export functionality
- `test_sales_export_api.py` - Sales export API endpoints
- `test_credit_payment_tracking.py` - Credit payment tracking
- `test_cash_on_hand_calculation.py` - Cash on hand calculations
- `test_cash_on_hand_simple.py` - Simplified cash tracking tests

### Customers
- `test_customer_export.py` - Customer export functionality
- `test_customer_export_api.py` - Customer export API endpoints
- `test_update_customer_endpoint.py` - Customer update endpoint tests
- `test_wholesale_retail.py` - Wholesale/retail customer types

### Inventory
- `test_inventory_export.py` - Inventory export functionality
- `test_stock_availability.py` - Stock availability checks
- `test_stock_adjustment_edit.py` - Stock adjustment editing
- `test_stock_adjustment_search_bug_fix.py` - Search bug fixes
- `test_storefront_creation.py` - Storefront creation logic
- `test_storefront_filtering.py` - Storefront filtering
- `test_multi_storefront_catalog.py` - Multi-storefront catalog
- `test_quantity_edit_rules.py` - Quantity editing rules

### Financial & Reporting
- `test_profit_calc.py` - Profit calculation logic
- `test_profit_proportional.py` - Proportional profit calculations
- `test_financial_summaries.py` - Financial summary reports
- `test_todays_stats_endpoint.py` - Today's statistics endpoint

### Exports
- `test_csv_exports.py` - CSV export functionality
- `test_pdf_exports.py` - PDF export functionality
- `test_audit_log_export.py` - Audit log export

### Receipts
- `test_receipt_generation.py` - Receipt generation logic

### Data Integrity
- `test_data_integrity.py` - Data integrity checks
- `test_serializer_fields.py` - Serializer field validation

### API & Search
- `test_search_endpoint.py` - Search endpoint functionality
- `test_url_patterns.py` - URL pattern verification

## Test File Naming Convention

All test files follow the pattern: `test_<feature_name>.py`

## Writing New Tests

When creating new test files:

1. **Name**: Use `test_<descriptive_name>.py`
2. **Location**: Place in this `tests/` directory
3. **Structure**: 
   ```python
   from django.test import TestCase
   
   class YourTestCase(TestCase):
       def setUp(self):
           # Setup test data
           pass
       
       def test_feature_description(self):
           # Test implementation
           pass
   ```

4. **Coverage**: Aim for comprehensive test coverage of:
   - Happy paths
   - Edge cases
   - Error handling
   - Validation logic

## Test Data

Tests should create their own test data in the `setUp()` method and clean up in `tearDown()` if needed. Django's TestCase automatically handles database rollback.

## Continuous Integration

These tests are run automatically on:
- Pre-commit hooks (if configured)
- Pull request creation
- Merge to development/main branches

## Best Practices

1. **Isolation**: Each test should be independent
2. **Descriptive Names**: Test names should clearly describe what they test
3. **AAA Pattern**: Arrange, Act, Assert
4. **Fast Execution**: Keep tests fast by using minimal data
5. **Clear Assertions**: Use descriptive assertion messages

## Coverage Goals

Maintain test coverage above:
- **Critical paths**: 100% (sales, payments, inventory)
- **Business logic**: 90%+
- **API endpoints**: 85%+
- **Overall project**: 80%+

## Related Documentation

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [DRF Testing Documentation](https://www.django-rest-framework.org/api-guide/testing/)
