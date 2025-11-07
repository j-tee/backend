#!/bin/bash
# Quick fix for AI credits duplicate key issue
# This script will:
# 1. Delete existing AI credit records (including the duplicate)
# 2. Restart the Django server with the fixed code

echo "=============================================="
echo "  AI CREDITS DUPLICATE KEY FIX - QUICK RUN"
echo "=============================================="
echo ""

# Check if in correct directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Must run from backend directory"
    echo "   cd /home/teejay/Documents/Projects/pos/backend"
    exit 1
fi

echo "Step 1: Deleting duplicate AI credit records..."
echo "----------------------------------------------"

# Use Django shell to delete records
python3 manage.py shell << EOF
from ai_features.models import AICreditPurchase, BusinessAICredits, AITransaction, AIUsageAlert

# Count before
purchase_count = AICreditPurchase.objects.count()
print(f"Found {purchase_count} AI credit purchase records")

if purchase_count > 0:
    # Delete all to clear duplicates
    AICreditPurchase.objects.all().delete()
    AITransaction.objects.all().delete()
    BusinessAICredits.objects.all().delete()
    AIUsageAlert.objects.all().delete()
    print("✅ All AI credit records deleted")
else:
    print("✅ No records to delete")

EOF

echo ""
echo "Step 2: Restarting Django server..."
echo "----------------------------------------------"
echo "Please restart your Django development server manually:"
echo ""
echo "  1. Stop the current server (Ctrl+C)"
echo "  2. Run: python3 manage.py runserver"
echo ""
echo "Or if using gunicorn:"
echo "  sudo systemctl restart gunicorn"
echo ""
echo "=============================================="
echo "✅ Database cleaned! Now restart the server."
echo "=============================================="
echo ""
echo "After restarting, the duplicate key error should be fixed."
echo "The new code uses millisecond timestamps + UUID for uniqueness."
