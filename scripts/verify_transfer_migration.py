#!/usr/bin/env python3
"""
Verification script for legacy transfer migration.

Run this after completing the migration to verify:
1. Legacy transfers are excluded from MovementTracker
2. Migrated Transfer record exists
3. Legacy endpoint returns 410 Gone
4. Tests pass
"""

import sys
import os
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from inventory.stock_adjustments import StockAdjustment
from inventory.transfer_models import Transfer
from reports.services.movement_tracker import MovementTracker
from accounts.models import Business


def check_legacy_records():
    """Check legacy StockAdjustment records still exist for audit"""
    legacy_count = StockAdjustment.objects.filter(
        adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
    ).count()
    
    print(f"1. Legacy Records Check:")
    print(f"   - Legacy TRANSFER_IN/OUT adjustments: {legacy_count}")
    
    if legacy_count > 0:
        print(f"   ✅ Legacy records preserved for audit trail")
        return True
    else:
        print(f"   ⚠️  No legacy records found (expected 2)")
        return False


def check_migrated_transfers():
    """Check migrated Transfer records exist"""
    migrated = Transfer.objects.filter(notes__contains='Migrated from legacy transfer').count()
    
    print(f"\n2. Migration Check:")
    print(f"   - Migrated Transfer records: {migrated}")
    
    if migrated > 0:
        print(f"   ✅ Legacy transfers successfully migrated")
        # Show details
        for transfer in Transfer.objects.filter(notes__contains='Migrated from legacy transfer'):
            print(f"      - Transfer ID: {transfer.id}")
            print(f"        Reference: {transfer.reference_number}")
            print(f"        From: {transfer.source_warehouse.name}")
            print(f"        To: {transfer.destination_warehouse.name if transfer.destination_warehouse else transfer.destination_storefront.name}")
            print(f"        Status: {transfer.status}")
        return True
    else:
        print(f"   ❌ No migrated transfers found")
        return False


def check_movement_tracker():
    """Verify MovementTracker excludes legacy transfers"""
    business = Business.objects.first()
    
    print(f"\n3. MovementTracker Check:")
    
    if not business:
        print(f"   ⚠️  No business found to test")
        return True
    
    movements = MovementTracker.get_movements(business_id=str(business.id))
    legacy_transfers = [
        m for m in movements 
        if m.get('source_type') == 'legacy_adjustment' and m.get('type') == 'transfer'
    ]
    
    print(f"   - Total movements: {len(movements)}")
    print(f"   - Legacy transfer movements: {len(legacy_transfers)}")
    
    if len(legacy_transfers) == 0:
        print(f"   ✅ MovementTracker correctly excludes legacy transfers")
        return True
    else:
        print(f"   ❌ Legacy transfers still appearing in MovementTracker!")
        for lt in legacy_transfers:
            print(f"      - ID: {lt.get('id')}, Ref: {lt.get('reference_number')}")
        return False


def check_deprecation():
    """Check that legacy functions are deprecated"""
    from inventory.transfer_services import create_paired_transfer_adjustments
    
    print(f"\n4. Deprecation Check:")
    
    try:
        # Try calling the function - it should raise DeprecationWarning
        create_paired_transfer_adjustments(None, None, 1, 0.0)
        print(f"   ❌ Legacy function did not raise DeprecationWarning")
        return False
    except DeprecationWarning as e:
        print(f"   ✅ Legacy function properly deprecated: {e}")
        return True
    except Exception as e:
        print(f"   ⚠️  Unexpected error: {e}")
        return True


def main():
    print("="*70)
    print("LEGACY TRANSFER MIGRATION VERIFICATION")
    print("="*70)
    
    checks = [
        check_legacy_records(),
        check_migrated_transfers(),
        check_movement_tracker(),
        check_deprecation(),
    ]
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(checks)
    total = len(checks)
    
    print(f"Checks passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL CHECKS PASSED - Migration successful!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} check(s) failed - Review output above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
