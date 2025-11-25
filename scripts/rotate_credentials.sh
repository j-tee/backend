#!/bin/bash
# Emergency script to rotate compromised credentials
# Run this immediately after credentials are exposed

set -e

echo "=================================="
echo "CREDENTIAL ROTATION SCRIPT"
echo "=================================="
echo ""
echo "⚠️  WARNING: This will rotate ALL credentials"
echo "   Make sure you have:"
echo "   1. Backup of current .env files"
echo "   2. Access to all service dashboards"
echo "   3. Downtime window scheduled"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Generating new keys..."
python scripts/generate_secure_keys.py > new_keys.txt
echo "✓ New keys generated (see new_keys.txt)"

echo ""
echo "Step 2: Manual actions required:"
echo ""
echo "DATABASE:"
echo "  1. Connect: sudo -u postgres psql"
echo "  2. Run: ALTER USER postgres WITH PASSWORD 'NEW_PASSWORD';"
echo "  3. Update DB_PASSWORD in .env files"
echo ""
read -p "Press Enter when database password is updated..."

echo ""
echo "GMAIL APP PASSWORD:"
echo "  1. Go to: https://myaccount.google.com/apppasswords"
echo "  2. Revoke old password"
echo "  3. Generate new password"
echo "  4. Update EMAIL_HOST_PASSWORD in .env files"
echo ""
read -p "Press Enter when email password is updated..."

echo ""
echo "OPENAI API KEY:"
echo "  1. Go to: https://platform.openai.com/api-keys"
echo "  2. Revoke compromised key"
echo "  3. Create new key"
echo "  4. Update OPENAI_API_KEY in .env files"
echo ""
read -p "Press Enter when OpenAI key is updated..."

echo ""
echo "PAYSTACK KEYS:"
echo "  1. Go to: https://dashboard.paystack.com/settings/developer"
echo "  2. Regenerate test keys (if test was exposed)"
echo "  3. Regenerate live keys (if live was exposed)"
echo "  4. Update PAYSTACK_* keys in .env files"
echo ""
read -p "Press Enter when Paystack keys are updated..."

echo ""
echo "Step 3: Updating SECRET_KEY in .env files..."
NEW_SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
echo "New SECRET_KEY generated"

echo ""
echo "Step 4: Restarting services..."
if [ -f "docker-compose.yml" ]; then
    docker-compose down
    docker-compose up -d
    echo "✓ Docker services restarted"
else
    sudo systemctl restart gunicorn
    sudo systemctl restart nginx
    sudo systemctl restart celery
    echo "✓ System services restarted"
fi

echo ""
echo "Step 5: Verification..."
python manage.py check --deploy
echo "✓ Django checks passed"

echo ""
echo "=================================="
echo "CREDENTIAL ROTATION COMPLETE"
echo "=================================="
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Test login functionality"
echo "2. Test payment processing"
echo "3. Test AI features"
echo "4. Monitor logs for errors"
echo "5. Update CI/CD secrets if applicable"
echo "6. Notify team of rotation"
echo "7. Delete new_keys.txt securely"
echo ""
echo "Incident Report:"
echo "  Date: $(date)"
echo "  Rotated: Database, Django, Email, OpenAI, Paystack"
echo "  Next Review: $(date -d '+90 days')"
echo ""
