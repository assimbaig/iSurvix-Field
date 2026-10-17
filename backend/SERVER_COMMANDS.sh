#!/bin/bash
# Quick Deployment Commands for GitHub-based deployment
# Run these commands on your server: 161.97.122.19

# ============================================
# STEP 1: Initial Server Setup
# ============================================

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv python3-dev nginx git certbot python3-certbot-nginx ufw build-essential

# ============================================
# STEP 2: Clone from GitHub
# ============================================

# Navigate to home directory
cd ~

# Clone your repository (replace YOUR_GITHUB_USERNAME and REPO_NAME)
git clone https://github.com/YOUR_GITHUB_USERNAME/REPO_NAME.git CHECKLIST_APP

# OR if repository is already named CHECKLIST_APP:
# git clone https://github.com/YOUR_GITHUB_USERNAME/CHECKLIST_APP.git

cd CHECKLIST_APP

# ============================================
# STEP 3: Setup Python Environment
# ============================================

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# ============================================
# STEP 4: Update Configuration Files
# ============================================

# Get current username
echo "Current user: $USER"
echo "Update the following files with this username..."

# Edit nginx config (replace YOUR_USER with actual username)
nano nginx_config.conf
# Change: /home/YOUR_USER/CHECKLIST_APP
# To:     /home/ACTUAL_USERNAME/CHECKLIST_APP

# Edit systemd service (replace YOUR_USER with actual username)
nano checklist.service
# Change: YOUR_USER
# To:     ACTUAL_USERNAME

# Edit deploy script (update APP_DIR, EMAIL)
nano deploy.sh
# Update: APP_DIR="/home/YOUR_USER/CHECKLIST_APP"
# Update: EMAIL="your-email@example.com"

# ============================================
# STEP 5: Create Required Directories
# ============================================

mkdir -p logs
mkdir -p media
mkdir -p staticfiles
sudo mkdir -p /var/log/gunicorn

# Set permissions
sudo chown -R $USER:www-data ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo chmod -R 775 ~/CHECKLIST_APP/media
sudo chmod -R 775 ~/CHECKLIST_APP/logs

# ============================================
# STEP 6: Database Setup
# ============================================

# Run migrations
python manage.py migrate

# Create superuser (will prompt for username/password)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# ============================================
# STEP 7: Setup Gunicorn Service
# ============================================

# Copy service file
sudo cp checklist.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable checklist

# Start the service
sudo systemctl start checklist

# Check status
sudo systemctl status checklist

# ============================================
# STEP 8: Setup Nginx
# ============================================

# Copy nginx config
sudo cp nginx_config.conf /etc/nginx/sites-available/checklist

# Create symbolic link
sudo ln -sf /etc/nginx/sites-available/checklist /etc/nginx/sites-enabled/

# Remove default nginx site
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl enable nginx
sudo systemctl restart nginx

# ============================================
# STEP 9: Setup SSL with Certbot
# ============================================

# Install SSL certificate
sudo certbot --nginx -d www.isurvix.com -d isurvix.com --email YOUR_EMAIL@example.com --agree-tos --redirect

# Test automatic renewal
sudo certbot renew --dry-run

# Enable automatic renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# ============================================
# STEP 10: Configure Firewall
# ============================================

# Allow necessary ports
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'

# Enable firewall
sudo ufw --force enable

# Check firewall status
sudo ufw status

# ============================================
# VERIFICATION
# ============================================

echo ""
echo "=========================================="
echo "DEPLOYMENT VERIFICATION"
echo "=========================================="
echo ""

# Check Gunicorn
echo "Gunicorn Status:"
sudo systemctl status checklist --no-pager
echo ""

# Check Nginx
echo "Nginx Status:"
sudo systemctl status nginx --no-pager
echo ""

# Check if app is running
echo "Testing local connection:"
curl http://127.0.0.1:8000 -I
echo ""

# Show SSL certificates
echo "SSL Certificates:"
sudo certbot certificates
echo ""

echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "✅ Application URL: https://www.isurvix.com"
echo "✅ Admin Panel: https://www.isurvix.com/admin"
echo ""
echo "📋 Useful Commands:"
echo "  - Restart app:    sudo systemctl restart checklist"
echo "  - View logs:      sudo journalctl -u checklist -f"
echo "  - Nginx reload:   sudo systemctl reload nginx"
echo "  - Update code:    cd ~/CHECKLIST_APP && git pull && sudo systemctl restart checklist"
echo ""
