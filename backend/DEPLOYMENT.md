# Production Deployment Guide
# Checklist Application - isurvix.com

## Server Details
- **Public IP:** 161.97.122.19
- **Domain:** www.isurvix.com / isurvix.com
- **SSL:** Let's Encrypt (Certbot)

## Prerequisites
1. Ubuntu/Debian server with root access
2. Python 3.9+
3. Domain DNS configured (A record pointing to 161.97.122.19)

## Deployment Steps

### 1. Upload Files to Server
```bash
# On your local machine
cd "/Users/sami/Desktop/CHECKLIST APP"
tar -czf checklist_app.tar.gz --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' --exclude='*.sqlite3' .

# Upload to server
scp checklist_app.tar.gz user@161.97.122.19:/home/YOUR_USER/
```

### 2. Setup on Server
```bash
# SSH into server
ssh user@161.97.122.19

# Extract files
cd /home/YOUR_USER
mkdir CHECKLIST_APP
cd CHECKLIST_APP
tar -xzf ../checklist_app.tar.gz

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

### 3. Configure Files
Edit the following files with correct paths:
```bash
# Update YOUR_USER in these files:
nano nginx_config.conf  # Replace YOUR_USER with actual username
nano checklist.service  # Replace YOUR_USER with actual username
nano deploy.sh          # Update APP_DIR, DOMAIN, EMAIL
```

### 4. Run Deployment Script
```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

### 5. Configure DNS
Add these DNS records at your domain registrar:

```
Type    Name    Value           TTL
A       @       161.97.122.19   3600
A       www     161.97.122.19   3600
```

## Manual Configuration (if needed)

### Gunicorn Service
```bash
sudo cp checklist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable checklist
sudo systemctl start checklist
```

### Nginx Configuration
```bash
sudo cp nginx_config.conf /etc/nginx/sites-available/checklist
sudo ln -s /etc/nginx/sites-available/checklist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### SSL Certificate (Certbot)
```bash
sudo certbot --nginx -d www.isurvix.com -d isurvix.com
```

## Maintenance Commands

### Application Management
```bash
# Restart application
sudo systemctl restart checklist

# View logs
sudo journalctl -u checklist -f

# Stop application
sudo systemctl stop checklist

# Check status
sudo systemctl status checklist
```

### Nginx Management
```bash
# Reload configuration
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx

# Test configuration
sudo nginx -t
```

### SSL Certificate Renewal
```bash
# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# View certificates
sudo certbot certificates
```

### Database Management
```bash
cd /home/YOUR_USER/CHECKLIST_APP
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### Update Application
```bash
cd /home/YOUR_USER/CHECKLIST_APP
source venv/bin/activate

# Pull latest changes (if using git)
git pull

# Install new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart application
sudo systemctl restart checklist
```

## File Locations

### Application Files
- App Directory: `/home/YOUR_USER/CHECKLIST_APP`
- Virtual Environment: `/home/YOUR_USER/CHECKLIST_APP/venv`
- Database: `/home/YOUR_USER/CHECKLIST_APP/db.sqlite3`
- Media Files: `/home/YOUR_USER/CHECKLIST_APP/media`
- Static Files: `/home/YOUR_USER/CHECKLIST_APP/staticfiles`

### Configuration Files
- Nginx: `/etc/nginx/sites-available/checklist`
- Systemd: `/etc/systemd/system/checklist.service`
- Gunicorn: `/home/YOUR_USER/CHECKLIST_APP/gunicorn_config.py`
- Django Settings: `/home/YOUR_USER/CHECKLIST_APP/checklist/settings.py`

### Log Files
- Application: `/home/YOUR_USER/CHECKLIST_APP/logs/app.log`
- Gunicorn Access: `/var/log/gunicorn/access.log`
- Gunicorn Error: `/var/log/gunicorn/error.log`
- Nginx Access: `/var/log/nginx/checklist_access.log`
- Nginx Error: `/var/log/nginx/checklist_error.log`
- Systemd: `sudo journalctl -u checklist`

### SSL Certificates
- Certificate: `/etc/letsencrypt/live/www.isurvix.com/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/www.isurvix.com/privkey.pem`

## Troubleshooting

### Application won't start
```bash
sudo journalctl -u checklist -n 50
sudo systemctl status checklist
```

### 502 Bad Gateway
```bash
# Check if Gunicorn is running
sudo systemctl status checklist

# Check Gunicorn logs
sudo tail -f /var/log/gunicorn/error.log
```

### Static files not loading
```bash
cd /home/YOUR_USER/CHECKLIST_APP
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### SSL certificate issues
```bash
sudo certbot certificates
sudo certbot renew --force-renewal
```

### Permission issues
```bash
sudo chown -R $USER:www-data /home/YOUR_USER/CHECKLIST_APP
sudo chmod -R 755 /home/YOUR_USER/CHECKLIST_APP
sudo chmod -R 775 /home/YOUR_USER/CHECKLIST_APP/media
```

## Security Checklist
- [x] DEBUG = False in settings.py
- [x] Strong SECRET_KEY in production
- [x] ALLOWED_HOSTS configured
- [x] SSL certificate installed
- [x] HTTPS redirect enabled
- [x] Security headers configured
- [x] Firewall (UFW) enabled
- [x] Only necessary ports open (80, 443, 22)
- [x] Regular backups configured
- [x] Keep system packages updated

## Backup Strategy
```bash
# Backup database
cd /home/YOUR_USER/CHECKLIST_APP
cp db.sqlite3 backups/db_$(date +%Y%m%d_%H%M%S).sqlite3

# Backup media files
tar -czf backups/media_$(date +%Y%m%d_%H%M%S).tar.gz media/

# Automate with cron
crontab -e
# Add: 0 2 * * * /path/to/backup_script.sh
```

## Support
For issues, check:
1. Application logs: `sudo journalctl -u checklist -f`
2. Nginx logs: `sudo tail -f /var/log/nginx/checklist_error.log`
3. Gunicorn logs: `sudo tail -f /var/log/gunicorn/error.log`
