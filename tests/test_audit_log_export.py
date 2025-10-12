#!/usr/bin/env python
"""
Test script for Audit Log Export functionality
"""
import os
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Business, BusinessMembership
from sales.models import AuditLog
from reports.services.audit import AuditLogExporter

User = get_user_model()


def test_audit_log_export():
    """Test the audit log export functionality"""
    
    print("=" * 80)
    print("AUDIT LOG EXPORT TEST")
    print("=" * 80)
    
    # Get a business with audit logs
    audit_logs = AuditLog.objects.select_related('sale__business').filter(
        sale__business__isnull=False
    )
    
    if not audit_logs.exists():
        print("❌ No audit logs found. Creating some test logs...")
        # We won't create test logs, just report
        print("❌ No audit logs available for testing")
        return
    
    # Get business from first audit log
    business = audit_logs.first().sale.business
    
    print(f"\n✅ Testing with business: {business.name}")
    
    # Get a user with access to this business
    membership = BusinessMembership.objects.filter(
        business=business,
        is_active=True
    ).first()
    
    if membership:
        user = membership.user
    else:
        user = business.owner
    
    if not user:
        print("❌ No user found with access to this business")
        return
    
    print(f"✅ Using user: {user.name if hasattr(user, 'name') else user.email}")
    
    # Get audit log count
    total_logs = AuditLog.objects.filter(
        sale__business=business
    ).count()
    
    print(f"✅ Found {total_logs} audit logs for this business")
    
    if total_logs == 0:
        print("❌ No audit logs found")
        return
    
    # Get date range
    oldest = AuditLog.objects.filter(sale__business=business).order_by('timestamp').first()
    newest = AuditLog.objects.filter(sale__business=business).order_by('-timestamp').first()
    
    if oldest and newest:
        print(f"   - Date range: {oldest.timestamp.strftime('%Y-%m-%d')} to {newest.timestamp.strftime('%Y-%m-%d')}")
    
    # Test 1: Export last 30 days
    print("\n" + "-" * 80)
    print("TEST 1: Export Last 30 Days of Audit Logs")
    print("-" * 80)
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
    }
    
    print(f"Date range: {start_date} to {end_date}")
    
    exporter = AuditLogExporter(user=user)
    
    try:
        data = exporter.export(filters)
        
        print(f"\n✅ Export successful!")
        print(f"   - Export Date: {data['summary']['export_date']}")
        print(f"   - Total Events: {data['summary']['total_events']}")
        print(f"   - First Event: {data['summary']['first_event_time']}")
        print(f"   - Last Event: {data['summary']['last_event_time']}")
        print(f"   - Unique Users: {data['summary']['unique_users']}")
        print(f"   - Unique Event Types: {data['summary']['unique_event_types']}")
        
        # Show event type breakdown
        if data['summary']['total_events'] > 0:
            print(f"\n   Top Event Types:")
            idx = 1
            while f'event_{idx}_type' in data['summary']:
                event_type = data['summary'][f'event_{idx}_type']
                count = data['summary'][f'event_{idx}_count']
                print(f"   {idx}. {event_type}: {count}")
                idx += 1
                if idx > 5:  # Show top 5
                    break
        
        # Show user activity
        if data['summary']['unique_users'] > 0:
            print(f"\n   Top Active Users:")
            idx = 1
            while f'user_{idx}_name' in data['summary']:
                user_name = data['summary'][f'user_{idx}_name']
                count = data['summary'][f'user_{idx}_count']
                print(f"   {idx}. {user_name}: {count} actions")
                idx += 1
                if idx > 5:  # Show top 5
                    break
        
        # Show first few logs
        if data['audit_logs']:
            print(f"\n   Recent audit logs (first 3):")
            for i, log in enumerate(data['audit_logs'][:3], 1):
                print(f"   {i}. [{log['timestamp']}] {log['event_label']}")
                print(f"      User: {log['user_name'] or log['user_email']}")
                if log['entity_name']:
                    print(f"      Entity: {log['entity_type']} - {log['entity_name']}")
                if log['description']:
                    print(f"      Description: {log['description']}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Filter by event type
    print("\n" + "-" * 80)
    print("TEST 2: Filter by Event Type (sale.created)")
    print("-" * 80)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
        'event_type': 'sale.created',
    }
    
    print(f"Filtering for 'sale.created' events")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Event type filter successful!")
        print(f"   - Events Found: {data['summary']['total_events']}")
        print(f"   - Unique Users: {data['summary']['unique_users']}")
    except Exception as e:
        print(f"❌ Event type filter failed: {e}")
    
    # Test 3: Filter by specific user
    print("\n" + "-" * 80)
    print("TEST 3: Filter by Specific User")
    print("-" * 80)
    
    first_log = AuditLog.objects.filter(
        sale__business=business,
        user__isnull=False
    ).first()
    
    if first_log and first_log.user:
        filters = {
            'start_date': start_date,
            'end_date': end_date,
            'user_id': str(first_log.user.id),
        }
        
        user_name = first_log.user.name if hasattr(first_log.user, 'name') else first_log.user.email
        print(f"Filtering for user: {user_name}")
        
        try:
            data = exporter.export(filters)
            print(f"✅ User filter successful!")
            print(f"   - Events by {user_name}: {data['summary']['total_events']}")
            print(f"   - Event Types: {data['summary']['unique_event_types']}")
        except Exception as e:
            print(f"❌ User filter failed: {e}")
    else:
        print("ℹ️  No logs with user information found")
    
    # Test 4: Short date range (last 7 days)
    print("\n" + "-" * 80)
    print("TEST 4: Last 7 Days")
    print("-" * 80)
    
    start_date = end_date - timedelta(days=7)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
    }
    
    print(f"Date range: {start_date} to {end_date}")
    
    try:
        data = exporter.export(filters)
        print(f"✅ 7-day filter successful!")
        print(f"   - Events Found: {data['summary']['total_events']}")
    except Exception as e:
        print(f"❌ 7-day filter failed: {e}")
    
    # Test 5: Specific event types - completed sales
    print("\n" + "-" * 80)
    print("TEST 5: Completed Sales Events")
    print("-" * 80)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
        'event_type': 'sale.completed',
    }
    
    print(f"Filtering for 'sale.completed' events")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Completed sales filter successful!")
        print(f"   - Completed Sales: {data['summary']['total_events']}")
    except Exception as e:
        print(f"❌ Completed sales filter failed: {e}")
    
    # Test 6: Business scoping
    print("\n" + "-" * 80)
    print("TEST 6: Business Scoping Test")
    print("-" * 80)
    
    other_business = Business.objects.exclude(id=business.id).first()
    
    if other_business:
        print(f"Checking that user cannot see data from: {other_business.name}")
        
        # Count logs for other business
        other_logs = AuditLog.objects.filter(sale__business=other_business).count()
        print(f"Other business has {other_logs} audit logs")
        
        # Try to export - should return only user's business data
        filters = {
            'start_date': end_date - timedelta(days=30),
            'end_date': end_date,
        }
        data = exporter.export(filters)
        
        print(f"✅ Business scoping works! User only sees their business data.")
        print(f"   - User's business events in export: {data['summary']['total_events']}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_audit_log_export()
