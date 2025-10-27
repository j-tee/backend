#!/bin/bash

# Script to check how Nginx is installed and managed

echo "Checking Nginx installation..."
echo "================================"

# Check if nginx is installed
if command -v nginx &> /dev/null; then
    echo "✓ Nginx is installed"
    
    # Get nginx version and configuration
    echo ""
    echo "Nginx version:"
    nginx -v 2>&1
    
    echo ""
    echo "Nginx configuration file location:"
    nginx -t 2>&1 | grep "configuration file"
    
    echo ""
    echo "Nginx binary location:"
    which nginx
    
    echo ""
    echo "Checking if Nginx is managed by systemd:"
    if systemctl list-unit-files | grep -q nginx.service; then
        echo "✓ Nginx is managed by systemd"
        systemctl status nginx --no-pager | head -n 5
    else
        echo "✗ Nginx is NOT managed by systemd"
    fi
    
    echo ""
    echo "Checking for init.d script:"
    if [ -f /etc/init.d/nginx ]; then
        echo "✓ Found init.d script at /etc/init.d/nginx"
    else
        echo "✗ No init.d script found"
    fi
    
    echo ""
    echo "Checking nginx process:"
    ps aux | grep -E '[n]ginx' | head -n 3
    
    echo ""
    echo "Nginx is likely controlled by:"
    if systemctl list-unit-files | grep -q nginx.service; then
        echo "  -> systemctl (start|stop|restart|reload) nginx"
    elif [ -f /etc/init.d/nginx ]; then
        echo "  -> service nginx (start|stop|restart|reload)"
        echo "  -> /etc/init.d/nginx (start|stop|restart|reload)"
    else
        echo "  -> nginx -s (stop|quit|reopen|reload)"
        echo "  -> Direct signals: kill -HUP \$(cat /var/run/nginx.pid)"
    fi
    
else
    echo "✗ Nginx is not installed or not in PATH"
fi

echo ""
echo "================================"
