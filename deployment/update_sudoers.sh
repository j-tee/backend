#!/bin/bash
# Run this script on the server to update sudoers configuration
# Usage: sudo bash update_sudoers.sh

echo "Updating sudoers configuration for deploy user..."

# Create sudoers file for deploy user
cat > /etc/sudoers.d/deploy << 'EOF'
# Allow deploy user to manage POS backend services without password

# Service management commands
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart posbackend
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart posbackend-celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart posbackend-celery-beat
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status posbackend
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status posbackend-celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status posbackend-celery-beat
deploy ALL=(ALL) NOPASSWD: /bin/systemctl enable posbackend
deploy ALL=(ALL) NOPASSWD: /bin/systemctl enable posbackend-celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl enable posbackend-celery-beat
deploy ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload

# Legacy service names (for backward compatibility)
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart celery-beat

# File operations for service files
deploy ALL=(ALL) NOPASSWD: /bin/cp -f /var/www/pos/backend/deployment/gunicorn.service /etc/systemd/system/posbackend.service
deploy ALL=(ALL) NOPASSWD: /bin/cp -f /var/www/pos/backend/deployment/celery.service /etc/systemd/system/posbackend-celery.service
deploy ALL=(ALL) NOPASSWD: /bin/cp -f /var/www/pos/backend/deployment/celery-beat.service /etc/systemd/system/posbackend-celery-beat.service

# Nginx management
deploy ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status nginx
deploy ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
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
    su - deploy -c "sudo systemctl status posbackend --no-pager | head -3" || \
    su - deploy -c "sudo systemctl status gunicorn --no-pager | head -3"
else
    echo "❌ Error in sudoers configuration! Removing the file..."
    rm /etc/sudoers.d/deploy
    exit 1
fi
