# Nginx + Gunicorn + Certbot Deployment

## 📋 Complete Server Commands (161.97.122.19)

### 1️⃣ Connect to Server
```bash
ssh root@161.97.122.19
```

### 2️⃣ Update System & Install All Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev nginx git certbot python3-certbot-nginx ufw
```

### 3️⃣ Clone from GitHub
```bash
cd ~
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git CHECKLIST_APP
cd CHECKLIST_APP
```

### 4️⃣ Setup Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5️⃣ Update Configuration Files
```bash
# The nginx_config.conf is ready to use with paths already set for /root/isurvix
# Just copy it in step 8 - Certbot will add SSL automatically
```

### 6️⃣ Setup Database
```bash
mkdir -p logs media staticfiles
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### 7️⃣ Setup Gunicorn Service
```bash
sudo cp checklist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable checklist
sudo systemctl start checklist

# If it fails, check the error:
sudo systemctl status checklist
sudo journalctl -xeu checklist.service

# Common fixes:
# 1. Make sure virtual environment exists
ls -la ~/CHECKLIST_APP/venv/bin/gunicorn

# 2. Check if paths are correct in service file
cat /etc/systemd/system/checklist.service

# 3. Test Gunicorn manually first:
cd ~/CHECKLIST_APP
source venv/bin/activate
gunicorn --config gunicorn_config.py checklist.wsgi:application
# Press Ctrl+C to stop, then try systemctl start again
```

### 8️⃣ Setup Nginx
```bash
sudo cp nginx_config.conf /etc/nginx/sites-available/checklist
sudo ln -sf /etc/nginx/sites-available/checklist /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t  # Should pass now (no SSL yet)
sudo systemctl enable nginx
sudo systemctl restart nginx
```

### 9️⃣ Setup SSL with Certbot (Like Flask!)
```bash
# Certbot will automatically add HTTPS config to Nginx and set up redirect
sudo certbot --nginx -d www.isurvix.com -d isurvix.com --email ftsamiullah@gmail.com --agree-tos --redirect

# Test auto-renewal
sudo certbot renew --dry-run

# Enable auto-renewal timer
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 🔟 Configure Firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status
```

### 1️⃣1️⃣ Set Permissions
```bash
sudo chown -R $USER:www-data ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo chmod -R 775 ~/CHECKLIST_APP/media
sudo chmod -R 775 ~/CHECKLIST_APP/logs
sudo chmod -R 775 ~/CHECKLIST_APP/staticfiles
```

---

## ✅ Verify Everything Works

```bash
# Check Gunicorn
sudo systemctl status checklist

# Check Nginx
sudo systemctl status nginx

# Check SSL certificate
sudo certbot certificates

# Test HTTPS
curl -I https://www.isurvix.com
```

---

## 🎯 Access Your Application

- **HTTPS:** https://www.isurvix.com
- **Admin:** https://www.isurvix.com/admin
- HTTP automatically redirects to HTTPS ✅

---

## 🔄 Update Application (Future Updates)

```bash
cd ~/CHECKLIST_APP
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart checklist
sudo systemctl reload nginx
```

---

## 📊 Useful Commands

### View Logs
```bash
# Application logs
sudo journalctl -u checklist -f

# Nginx access logs
sudo tail -f /var/log/nginx/checklist_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/checklist_error.log
```

### Service Management
```bash
# Restart application
sudo systemctl restart checklist

# Reload Nginx (for config changes)
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx
```

### SSL Certificate Management
```bash
# View certificates
sudo certbot certificates

# Renew certificates manually
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run

# Force renewal (if needed)
sudo certbot renew --force-renewal
```

---

## 🐛 Troubleshooting

### 502 Bad Gateway
```bash
# Check if Gunicorn is running
sudo systemctl status checklist
sudo journalctl -u checklist -n 50

# Check Nginx logs
sudo tail -f /var/log/nginx/checklist_error.log
```

### SSL Certificate Issues
```bash
sudo certbot certificates
sudo certbot delete --cert-name www.isurvix.com
sudo certbot --nginx -d www.isurvix.com -d isurvix.com
```

### Static Files Not Loading
```bash
cd ~/CHECKLIST_APP
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl reload nginx
```

---

## 🎉 Complete Setup

**Architecture:**
```
Internet (HTTPS:443)
    ↓
Nginx (SSL Termination)
    ↓
Gunicorn (127.0.0.1:8000)
    ↓
Django Application
```

**Features:**
- ✅ HTTPS with Let's Encrypt SSL
- ✅ Auto-renewing certificates
- ✅ HTTP → HTTPS redirect
- ✅ Nginx serves static/media files
- ✅ Gunicorn runs Django
- ✅ Auto-starts on reboot
- ✅ Firewall configured

Just like your Flask setup! 🚀
