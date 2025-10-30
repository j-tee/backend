#!/bin/bash
# Run this script on the server to update sudoers configuration
# Usage: sudo bash update_sudoers.sh

echo "Updating sudoers configuration for deploy user..."

# Create sudoers file for deploy user
cat > /etc/sudoers.d/deploy << 'EOF'
# Allow deploy user to manage POS backend services without password
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery-beat
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status gunicorn
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status celery-beat
deploy ALL=(ALL) NOPASSWD: /opt/nginx/sbin/nginx -t
deploy ALL=(ALL) NOPASSWD: /opt/nginx/sbin/nginx -s reload
deploy ALL=(ALL) NOPASSWD: /opt/nginx/sbin/nginx -s *
EOF

# Set proper permissions
chmod 0440 /etc/sudoers.d/deploy

# Validate sudoers configuration
if visudo -c -f /etc/sudoers.d/deploy; then
    echo "✅ Sudoers configuration updated successfully!"
    echo ""
    echo "Testing passwordless sudo:"
    su - deploy -c "sudo systemctl status gunicorn --no-pager | head -3"
else
    echo "❌ Error in sudoers configuration! Removing the file..."
    rm /etc/sudoers.d/deploy
    exit 1
fi
