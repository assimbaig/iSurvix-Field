# Gunicorn-Only Deployment (Simple Setup)

## 📋 Quick Commands for Server (161.97.122.19)

### 1️⃣ Connect to Server
```bash
ssh root@161.97.122.19
```

### 2️⃣ Update System & Install Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev git ufw
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

### 5️⃣ Update Configuration File
```bash
# Get your username
echo $USER

# Edit systemd service
nano checklist.service
```
Replace `YOUR_USER` with your actual username (shown by echo command)

### 6️⃣ Create Directories
```bash
mkdir -p logs media staticfiles
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

### 9️⃣ Configure Firewall
```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000
sudo ufw --force enable
sudo ufw status
```

### 🔟 Set Permissions
```bash
sudo chown -R $USER:$USER ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo chmod -R 775 ~/CHECKLIST_APP/media
sudo chmod -R 775 ~/CHECKLIST_APP/logs
```

---

## ✅ Access Your Application

- **HTTP:** http://161.97.122.19:8000
- **Domain (if DNS configured):** http://www.isurvix.com:8000

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

## 📊 Useful Commands

### View Logs
```bash
# Application logs (live)
sudo journalctl -u checklist -f

# Last 50 lines
sudo journalctl -u checklist -n 50
```

### Service Management
```bash
# Restart application
sudo systemctl restart checklist

# Stop application
sudo systemctl stop checklist

# Start application
sudo systemctl start checklist

# Check status
sudo systemctl status checklist
```

### Database Backup
```bash
cd ~/CHECKLIST_APP
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d)
```

---

## 🐛 Troubleshooting

### Application won't start
```bash
sudo systemctl status checklist
sudo journalctl -u checklist -n 50
```

### Cannot access application
```bash
# Check if Gunicorn is running
sudo systemctl status checklist

# Check if port is open
sudo ufw status

# Test local connection
curl http://127.0.0.1:8000

# Check if process is listening
sudo netstat -tulpn | grep 8000
```

### Permission errors
```bash
sudo chown -R $USER:$USER ~/CHECKLIST_APP
sudo chmod -R 755 ~/CHECKLIST_APP
sudo systemctl restart checklist
```

---

## 🎯 Expected Results

After successful deployment:
- ✅ Visit **http://161.97.122.19:8000** → Should show login page
- ✅ Visit **http://161.97.122.19:8000/admin** → Admin panel
- ✅ Application running on port 8000
- ✅ Auto-starts on server reboot

---

## 📝 Notes

**This setup uses:**
- ✅ Gunicorn only (no Nginx)
- ✅ HTTP only (no SSL)
- ✅ Port 8000

**To add SSL/HTTPS later:**
- Use Cloudflare for free SSL
- Or add Nginx reverse proxy with Certbot
- Or use a cloud load balancer with SSL termination

**Security Reminder:**
- Static files served by Gunicorn (slower than Nginx)
- No HTTPS (data transmitted in plain text)
- Consider adding Nginx + SSL for production use
