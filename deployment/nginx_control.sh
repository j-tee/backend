#!/bin/bash

# Nginx Control Helper Script
# Handles Nginx whether it's managed by systemd, init.d, or compiled from source

ACTION=$1

if [ -z "$ACTION" ]; then
    echo "Usage: $0 {start|stop|restart|reload|status|test}"
    exit 1
fi

# Function to reload/restart Nginx based on how it's managed
nginx_action() {
    local action=$1
    
    # Check if Nginx is managed by systemd
    if systemctl list-unit-files 2>/dev/null | grep -q nginx.service; then
        echo "Using systemd to $action Nginx..."
        case $action in
            start)
                sudo systemctl start nginx
                ;;
            stop)
                sudo systemctl stop nginx
                ;;
            restart)
                sudo systemctl restart nginx
                ;;
            reload)
                sudo systemctl reload nginx
                ;;
            status)
                sudo systemctl status nginx --no-pager
                ;;
            test)
                sudo nginx -t
                ;;
        esac
        return $?
    fi
    
    # Check if there's an init.d script
    if [ -f /etc/init.d/nginx ]; then
        echo "Using init.d script to $action Nginx..."
        case $action in
            start|stop|restart|reload|status)
                sudo /etc/init.d/nginx $action
                ;;
            test)
                sudo nginx -t
                ;;
        esac
        return $?
    fi
    
    # Fall back to nginx signals (for source-compiled nginx)
    echo "Using nginx signals to $action Nginx..."
    
    # First, test configuration
    if [ "$action" != "status" ] && [ "$action" != "test" ]; then
        if ! sudo nginx -t 2>/dev/null; then
            echo "ERROR: Nginx configuration test failed!"
            return 1
        fi
    fi
    
    case $action in
        start)
            if pgrep nginx >/dev/null; then
                echo "Nginx is already running"
                return 0
            fi
            sudo nginx
            ;;
        stop)
            # Graceful shutdown
            sudo nginx -s quit
            ;;
        restart)
            # Stop and start
            if pgrep nginx >/dev/null; then
                sudo nginx -s quit
                sleep 2
            fi
            sudo nginx
            ;;
        reload)
            # Reload configuration without dropping connections
            if pgrep nginx >/dev/null; then
                sudo nginx -s reload
            else
                echo "Nginx is not running, starting it..."
                sudo nginx
            fi
            ;;
        status)
            if pgrep nginx >/dev/null; then
                echo "Nginx is running"
                ps aux | grep -E '[n]ginx' | head -n 3
                return 0
            else
                echo "Nginx is not running"
                return 3
            fi
            ;;
        test)
            sudo nginx -t
            ;;
    esac
    
    return $?
}

# Execute the action
nginx_action "$ACTION"
exit_code=$?

# Show status after action (except for status and test commands)
if [ "$ACTION" != "status" ] && [ "$ACTION" != "test" ] && [ $exit_code -eq 0 ]; then
    echo ""
    echo "Verifying Nginx is running..."
    if pgrep nginx >/dev/null; then
        echo "✓ Nginx is running"
    else
        echo "✗ WARNING: Nginx may not be running!"
        exit_code=1
    fi
fi

exit $exit_code
