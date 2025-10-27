# Nginx Setup for Source-Compiled Installations

## Overview

If your Nginx was compiled from source, it won't be managed by systemd by default. This guide shows you how to either:
1. Create a systemd service for your source-compiled Nginx
2. Use Nginx directly with signals

## Option 1: Create Systemd Service (Recommended)

### Step 1: Find Your Nginx Installation

```bash
# Find nginx binary
which nginx

# Check nginx version and compile options
nginx -V

# Find nginx configuration directory
nginx -t 2>&1 | grep "configuration file"
```

### Step 2: Create Systemd Service File

Create `/etc/systemd/system/nginx.service`:

```bash
sudo nano /etc/systemd/system/nginx.service
```

Add the following content (adjust paths based on your installation):

```ini
[Unit]
Description=The nginx HTTP and reverse proxy server
After=network.target remote-fs.target nss-lookup.target

[Service]
Type=forking
PIDFile=/var/run/nginx.pid
# Nginx will fail to start if /var/run/nginx.pid already exists but has the wrong
# SELinux context. This might happen when running `nginx -t` from the cmdline.
# https://bugzilla.redhat.com/show_bug.cgi?id=1268621
ExecStartPre=/usr/bin/rm -f /var/run/nginx.pid
ExecStartPre=/usr/local/nginx/sbin/nginx -t
ExecStart=/usr/local/nginx/sbin/nginx
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s QUIT $MAINPID
KillSignal=SIGQUIT
TimeoutStopSec=5
KillMode=mixed
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Important:** Adjust these paths based on your actual nginx installation:
- `/usr/local/nginx/sbin/nginx` - Your nginx binary path (use `which nginx`)
- `/var/run/nginx.pid` - Your PID file location (check `nginx -V` output)

### Step 3: Find Nginx Paths

```bash
# Get nginx paths from compilation
nginx -V 2>&1 | grep -o '\-\-[^=]*=[^ ]*'

# Common paths to check:
# --prefix=/usr/local/nginx
# --conf-path=/etc/nginx/nginx.conf
# --pid-path=/var/run/nginx.pid
# --sbin-path=/usr/local/nginx/sbin/nginx
```

### Step 4: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable nginx to start on boot
sudo systemctl enable nginx

# Start nginx
sudo systemctl start nginx

# Check status
sudo systemctl status nginx

# Test reload
sudo systemctl reload nginx
```

## Option 2: Use Nginx Signals Directly

If you prefer not to use systemd, control Nginx with signals:

### Configuration Test
```bash
sudo nginx -t
```

### Start Nginx
```bash
sudo nginx
```

### Reload Configuration (Graceful)
```bash
sudo nginx -s reload
```

### Graceful Shutdown
```bash
sudo nginx -s quit
```

### Fast Shutdown
```bash
sudo nginx -s stop
```

### Reopen Log Files
```bash
sudo nginx -s reopen
```

### Check if Nginx is Running
```bash
pgrep nginx
# or
ps aux | grep nginx
```

### Kill Nginx Process
```bash
# Get master process PID
cat /var/run/nginx.pid

# Send signal
sudo kill -QUIT $(cat /var/run/nginx.pid)  # Graceful shutdown
sudo kill -HUP $(cat /var/run/nginx.pid)   # Reload config
```

## Option 3: Create Init.d Script

If you want to use `service nginx` commands, create an init.d script:

```bash
sudo nano /etc/init.d/nginx
```

Add this content (adjust paths):

```bash
#!/bin/sh
### BEGIN INIT INFO
# Provides:          nginx
# Required-Start:    $local_fs $remote_fs $network $syslog $named
# Required-Stop:     $local_fs $remote_fs $network $syslog $named
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: starts the nginx web server
# Description:       starts nginx using start-stop-daemon
### END INIT INFO

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
DAEMON=/usr/local/nginx/sbin/nginx
NAME=nginx
DESC=nginx

# Include nginx defaults if available
if [ -r /etc/default/nginx ]; then
    . /etc/default/nginx
fi

DAEMON_OPTS="-c /etc/nginx/nginx.conf"

test -x $DAEMON || exit 0

. /lib/init/vars.sh
. /lib/lsb/init-functions

# Try to extract nginx pidfile
PID=$(cat /var/run/nginx.pid 2>/dev/null)
if [ -z "$PID" ]; then
    PID=/var/run/nginx.pid
fi

case "$1" in
    start)
        echo -n "Starting $DESC: "
        start-stop-daemon --start --quiet --pidfile $PID \
            --exec $DAEMON -- $DAEMON_OPTS || true
        echo "$NAME."
        ;;

    stop)
        echo -n "Stopping $DESC: "
        start-stop-daemon --stop --quiet --pidfile $PID \
            --exec $DAEMON || true
        echo "$NAME."
        ;;

    restart|force-reload)
        echo -n "Restarting $DESC: "
        start-stop-daemon --stop --quiet --pidfile $PID \
            --exec $DAEMON || true
        sleep 1
        start-stop-daemon --start --quiet --pidfile $PID \
            --exec $DAEMON -- $DAEMON_OPTS || true
        echo "$NAME."
        ;;

    reload)
        echo -n "Reloading $DESC configuration: "
        start-stop-daemon --stop --signal HUP --quiet --pidfile $PID \
            --exec $DAEMON || true
        echo "$NAME."
        ;;

    status)
        status_of_proc -p $PID "$DAEMON" nginx && exit 0 || exit $?
        ;;

    *)
        echo "Usage: $NAME {start|stop|restart|reload|force-reload|status}" >&2
        exit 1
        ;;
esac

exit 0
```

Make it executable:
```bash
sudo chmod +x /etc/init.d/nginx
sudo update-rc.d nginx defaults
```

Now you can use:
```bash
sudo service nginx start
sudo service nginx stop
sudo service nginx restart
sudo service nginx reload
sudo service nginx status
```

## Using Our Deployment Scripts

Our deployment scripts (`nginx_control.sh`) automatically detect how your Nginx is managed and use the appropriate method:

```bash
# Test nginx configuration
./deployment/nginx_control.sh test

# Reload nginx (auto-detects management method)
./deployment/nginx_control.sh reload

# Restart nginx
./deployment/nginx_control.sh restart

# Check status
./deployment/nginx_control.sh status
```

The script will:
1. First try systemd (`systemctl`)
2. Then try init.d script (`/etc/init.d/nginx`)
3. Fall back to direct signals (`nginx -s`)

## Verifying Your Setup

After setting up, verify everything works:

```bash
# Check nginx is running
pgrep nginx

# Test configuration
sudo nginx -t

# Try reload
./deployment/nginx_control.sh reload

# Check logs
tail -f /var/log/nginx/error.log
```

## Troubleshooting

### Nginx won't start
```bash
# Check configuration
sudo nginx -t

# Check if already running
pgrep nginx

# Check error log
tail -f /var/log/nginx/error.log

# Check port 80 is not in use
sudo lsof -i :80
```

### Permission denied
```bash
# Nginx needs to bind to port 80 (requires root)
sudo nginx

# Or use systemd
sudo systemctl start nginx
```

### PID file issues
```bash
# Remove stale PID file
sudo rm /var/run/nginx.pid

# Start fresh
sudo nginx
```

## Recommended Approach

For production deployment, **Option 1 (Systemd Service)** is recommended because:
- Consistent with other services
- Automatic startup on reboot
- Better logging integration
- Standard service management commands
- Works with our CI/CD scripts

## Configuration Locations

Common nginx paths (check yours with `nginx -V`):

```bash
# Configuration file
/etc/nginx/nginx.conf
/usr/local/nginx/conf/nginx.conf

# Site configurations
/etc/nginx/sites-available/
/etc/nginx/sites-enabled/

# PID file
/var/run/nginx.pid
/usr/local/nginx/logs/nginx.pid

# Error log
/var/log/nginx/error.log
/usr/local/nginx/logs/error.log

# Access log
/var/log/nginx/access.log
/usr/local/nginx/logs/access.log
```

## Next Steps

1. Determine which option you prefer
2. If using systemd (recommended), create the service file with correct paths
3. Test the setup
4. Update deployment scripts will automatically work

The deployment scripts we created will work regardless of which method you choose!
