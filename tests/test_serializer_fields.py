#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.serializers import SaleSerializer

# Create a serializer instance
serializer = SaleSerializer()

print("\n" + "="*60)
print("SALESSERIALIZER FIELD ANALYSIS")
print("="*60)

print("\n📋 All Fields:")
for field_name, field_obj in serializer.fields.items():
    is_readonly = field_obj.read_only
    is_required = field_obj.required if hasattr(field_obj, 'required') else 'N/A'
    print(f"   {field_name:30} | read_only={is_readonly:<5} | required={is_required}")

print("\n✅ Read-Only Fields (should NOT be in request):")
for field_name, field_obj in serializer.fields.items():
    if field_obj.read_only:
        print(f"   ✓ {field_name}")

print("\n📝 Writable Fields (CAN be in request):")
for field_name, field_obj in serializer.fields.items():
    if not field_obj.read_only:
        is_required = '(REQUIRED)' if getattr(field_obj, 'required', False) else '(optional)'
        print(f"   • {field_name:30} {is_required}")

print("\n🎯 Key Fields Check:")
fields_to_check = ['amount_paid', 'amount_refunded', 'amount_due', 'total_amount', 
                   'subtotal', 'discount_amount', 'tax_amount']
for field_name in fields_to_check:
    if field_name in serializer.fields:
        field = serializer.fields[field_name]
        status = "✅ READ-ONLY" if field.read_only else "❌ WRITABLE"
        print(f"   {field_name:20} {status}")

print("\n" + "="*60)
print("✅ Serializer configuration loaded successfully!")
print("="*60 + "\n")
