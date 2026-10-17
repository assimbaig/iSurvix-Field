#!/bin/bash

# Deployment script for Checklist Application
# Run this on your production server (161.97.122.19)

echo "🚀 Starting deployment for isurvix.com..."

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Variables - UPDATE THESE!
APP_DIR="/home/YOUR_USER/CHECKLIST_APP"
DOMAIN="www.isurvix.com"
EMAIL="your-email@example.com"  # For Certbot notifications

echo -e "${YELLOW}⚠️  Before running this script:${NC}"
echo "1. Update APP_DIR, DOMAIN, and EMAIL variables in this script"
echo "2. Update YOUR_USER in nginx_config.conf and checklist.service"
echo "3. Make sure you're running as sudo or have sudo privileges"
read -p "Press Enter to continue or Ctrl+C to exit..."

# Update system
echo -e "\n${GREEN}📦 Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# Install required packages
echo -e "\n${GREEN}📦 Installing required packages...${NC}"
sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx

# Install Gunicorn
echo -e "\n${GREEN}📦 Installing Gunicorn...${NC}"
pip install gunicorn

# Create necessary directories
echo -e "\n${GREEN}📁 Creating directories...${NC}"
sudo mkdir -p /var/log/gunicorn
sudo mkdir -p $APP_DIR/staticfiles
sudo mkdir -p $APP_DIR/media
sudo mkdir -p $APP_DIR/logs

# Collect static files
echo -e "\n${GREEN}🎨 Collecting static files...${NC}"
cd $APP_DIR
source venv/bin/activate
python manage.py collectstatic --noinput

# Run migrations
echo -e "\n${GREEN}🗄️  Running database migrations...${NC}"
python manage.py migrate

# Set permissions
echo -e "\n${GREEN}🔐 Setting permissions...${NC}"
sudo chown -R $USER:www-data $APP_DIR
sudo chmod -R 755 $APP_DIR
sudo chmod -R 775 $APP_DIR/media
sudo chmod -R 775 $APP_DIR/logs
sudo chmod -R 775 $APP_DIR/staticfiles

# Copy systemd service file
echo -e "\n${GREEN}⚙️  Setting up systemd service...${NC}"
sudo cp $APP_DIR/checklist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable checklist
sudo systemctl start checklist
sudo systemctl status checklist

# Configure Nginx
echo -e "\n${GREEN}🌐 Configuring Nginx...${NC}"
sudo cp $APP_DIR/nginx_config.conf /etc/nginx/sites-available/checklist
sudo ln -sf /etc/nginx/sites-available/checklist /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# Start Nginx
echo -e "\n${GREEN}🚀 Starting Nginx...${NC}"
sudo systemctl enable nginx
sudo systemctl restart nginx

# Setup SSL with Certbot
echo -e "\n${GREEN}🔒 Setting up SSL certificate with Certbot...${NC}"
sudo certbot --nginx -d $DOMAIN -d isurvix.com --non-interactive --agree-tos --email $EMAIL --redirect

# Setup automatic SSL renewal
echo -e "\n${GREEN}🔄 Setting up automatic SSL renewal...${NC}"
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Configure firewall
echo -e "\n${GREEN}🔥 Configuring firewall...${NC}"
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw --force enable

# Final checks
echo -e "\n${GREEN}✅ Running final checks...${NC}"
echo "Gunicorn status:"
sudo systemctl status checklist --no-pager
echo ""
echo "Nginx status:"
sudo systemctl status nginx --no-pager
echo ""
echo "SSL certificate status:"
sudo certbot certificates

echo -e "\n${GREEN}🎉 Deployment complete!${NC}"
echo -e "\n${YELLOW}📋 Next steps:${NC}"
echo "1. Point your domain DNS A record to: 161.97.122.19"
echo "2. Visit https://www.isurvix.com to test"
echo "3. Check logs at: /var/log/gunicorn/ and /var/log/nginx/"
echo ""
echo -e "${YELLOW}⚙️  Useful commands:${NC}"
echo "  Restart app:    sudo systemctl restart checklist"
echo "  View logs:      sudo journalctl -u checklist -f"
echo "  Nginx reload:   sudo systemctl reload nginx"
echo "  Test SSL:       sudo certbot renew --dry-run"
