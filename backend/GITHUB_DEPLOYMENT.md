# GitHub Deployment - Quick Reference

## 📋 Complete Command List for Server (161.97.122.19)

### BEFORE YOU START:
1. Push all files to GitHub repository
2. Make sure DNS A records point to 161.97.122.19:
   - `isurvix.com` → `161.97.122.19`
   - `www.isurvix.com` → `161.97.122.19`

---

## 🚀 Run These Commands on Server

### 1️⃣ Connect to Server
```bash
ssh root@161.97.122.19
# OR
ssh your_username@161.97.122.19
```

### 2️⃣ Update System & Install Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev nginx git certbot python3-certbot-nginx ufw build-essential
```

### 3️⃣ Clone from GitHub
```bash
cd ~
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME.git CHECKLIST_APP
cd CHECKLIST_APP
```

### 4️⃣ Setup Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5️⃣ Update Configuration Files

**Get your username:**
```bash
echo $USER
```

**Edit nginx_config.conf:**
```bash
nano nginx_config.conf
```
Replace all instances of `/home/YOUR_USER/CHECKLIST_APP` with `/home/ACTUAL_USERNAME/CHECKLIST_APP`

**Edit checklist.service:**
```bash
nano checklist.service
```
Replace `YOUR_USER` with your actual username

**Edit deploy.sh:**
```bash
nano deploy.sh
```
Update:
- `APP_DIR="/home/YOUR_USER/CHECKLIST_APP"` → Use your actual username
- `EMAIL="your-email@example.com"` → Your actual email

### 6️⃣ Create Directories
```bash
mkdir -p logs media staticfiles
sudo mkdir -p /var/log/gunicorn
```

### 7️⃣ Setup Database
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### 8️⃣ Setup Gunicorn Service
```bash
sudo cp checklist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable checklist
sudo systemctl start checklist
sudo systemctl status checklist
```

### 9️⃣ Setup Nginx
```bash
sudo cp nginx_config.conf /etc/nginx/sites-available/checklist
sudo ln -sf /etc/nginx/sites-available/checklist /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

### 🔟 Setup SSL Certificate
```bash
sudo certbot --nginx -d www.isurvix.com -d isurvix.com --email your@email.com --agree-tos --redirect
sudo certbot renew --dry-run
sudo systemctl enable certbot.timer
```

### 1️⃣1️⃣ Configure Firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status
```

### 1️⃣2️⃣ Set Permissions
```bash
sudo chown -R $USER:www-data ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo chmod -R 775 ~/CHECKLIST_APP/media
sudo chmod -R 775 ~/CHECKLIST_APP/logs
sudo chmod -R 775 ~/CHECKLIST_APP/staticfiles
```

---

## ✅ Verify Deployment

```bash
# Check application status
sudo systemctl status checklist

# Check Nginx status
sudo systemctl status nginx

# View application logs
sudo journalctl -u checklist -f

# Test local connection
curl http://127.0.0.1:8000 -I

# Check SSL certificates
sudo certbot certificates
```

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
```

---

## 📊 Useful Management Commands

### View Logs
```bash
# Application logs (live)
sudo journalctl -u checklist -f

# Nginx access logs
sudo tail -f /var/log/nginx/checklist_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/checklist_error.log

# Gunicorn logs
sudo tail -f /var/log/gunicorn/error.log
```

### Service Management
```bash
# Restart application
sudo systemctl restart checklist

# Stop application
sudo systemctl stop checklist

# Start application
sudo systemctl start checklist

# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx
```

### Database Management
```bash
cd ~/CHECKLIST_APP
source venv/bin/activate

# Create backup
cp db.sqlite3 db.sqlite3.backup

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

---

## 🐛 Troubleshooting

### Application won't start
```bash
sudo systemctl status checklist
sudo journalctl -u checklist -n 50
```

### 502 Bad Gateway
```bash
sudo systemctl status checklist
sudo tail -f /var/log/gunicorn/error.log
curl http://127.0.0.1:8000
```

### Static files not loading
```bash
cd ~/CHECKLIST_APP
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart nginx
```

### Permission errors
```bash
sudo chown -R $USER:www-data ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo chmod -R 775 ~/CHECKLIST_APP/media
sudo systemctl restart checklist
```

### SSL certificate issues
```bash
sudo certbot certificates
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

---

## 🎯 Expected Results

After successful deployment:
- ✅ Visit **https://www.isurvix.com** → Should show login page
- ✅ Visit **https://isurvix.com** → Should redirect to www and HTTPS
- ✅ HTTP automatically redirects to HTTPS
- ✅ SSL certificate valid
- ✅ Admin panel accessible at **/admin**

---

## 📞 Quick Commands Reference

```bash
# View all services
sudo systemctl status checklist nginx

# Restart everything
sudo systemctl restart checklist nginx

# View real-time logs
sudo journalctl -u checklist -f

# Check disk space
df -h

# Check memory usage
free -h

# Check running processes
ps aux | grep gunicorn
```
