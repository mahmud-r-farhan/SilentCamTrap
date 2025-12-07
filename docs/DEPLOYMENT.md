# 🚀 Deployment Guide

Complete guide for deploying SilentCamTrap in production environments.

---

## Table of Contents

1. [Server Requirements](#server-requirements)
2. [Deployment Options](#deployment-options)
3. [Docker Deployment](#docker-deployment)
4. [VPS Deployment](#vps-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [SSL/HTTPS Setup](#sslhttps-setup)
7. [Domain Configuration](#domain-configuration)
8. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Server Requirements

### Minimum Requirements
| Resource | Specification |
|----------|---------------|
| CPU | 1 vCPU |
| RAM | 1 GB |
| Storage | 10 GB SSD |
| OS | Ubuntu 20.04+ / Debian 11+ |

### Recommended Requirements
| Resource | Specification |
|----------|---------------|
| CPU | 2 vCPUs |
| RAM | 2 GB |
| Storage | 50 GB SSD |
| OS | Ubuntu 22.04 LTS |

### Required Software
- Docker 20.10+ & Docker Compose 2.0+
- OR Node.js 18+ & npm 9+

---

## Deployment Options

### Option 1: Docker (Recommended) ⭐
Best for: Most deployments, easy updates, consistent environment

### Option 2: Direct Node.js
Best for: Minimal resource usage, custom configurations

### Option 3: Cloud Platforms
Best for: Scalability, managed infrastructure (AWS, DigitalOcean, etc.)

---

## Docker Deployment

### Step 1: Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### Step 2: Clone Repository

```bash
# Clone the repository
git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git
cd SilentCamTrap/server
```

### Step 3: Configure Environment

```bash
# Copy and edit environment file
cp .env.example .env
nano .env
```

**Production .env Settings:**
```env
NODE_ENV=production
PORT=3000
SESSION_SECRET=<generate-random-64-char-string>
API_KEY=<generate-random-32-char-string>
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=<generate-strong-password>
ENABLE_AUTH=true
ENABLE_RATE_LIMIT=true
MAX_FILE_SIZE_MB=10
```

**Generate Secure Secrets:**
```bash
# Generate session secret
openssl rand -hex 32

# Generate API key
openssl rand -hex 16
```

### Step 4: Deploy with Docker Compose

```bash
# Build and start containers
docker compose up -d

# Verify container is running
docker compose ps

# View logs
docker compose logs -f
```

### Step 5: Configure Firewall

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# If accessing directly on port 3000
sudo ufw allow 3000/tcp

# Enable firewall
sudo ufw enable
```

---

## VPS Deployment

### Without Docker

```bash
# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2 for process management
sudo npm install -g pm2

# Clone and setup
git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git
cd SilentCamTrap/server
npm ci --only=production

# Configure environment
cp .env.example .env
nano .env

# Start with PM2
pm2 start src/server.js --name silentcamtrap
pm2 save
pm2 startup
```

---

## Cloud Deployment

### DigitalOcean App Platform

1. Fork repository to your GitHub
2. Create new App in DigitalOcean
3. Connect GitHub repository
4. Configure:
   - **Source:** `server` directory
   - **Build Command:** `npm ci`
   - **Run Command:** `npm start`
5. Set environment variables
6. Deploy

### AWS EC2

1. Launch EC2 instance (t3.small recommended)
2. SSH into instance
3. Follow Docker deployment steps
4. Configure Security Group for ports 80, 443, 3000

### Heroku

```bash
# Install Heroku CLI and login
heroku login

# Create app
heroku create silentcamtrap

# Set environment variables
heroku config:set NODE_ENV=production
heroku config:set SESSION_SECRET=your-secret
heroku config:set API_KEY=your-api-key

# Deploy
git subtree push --prefix server heroku main
```

---

## SSL/HTTPS Setup

### Using Nginx + Let's Encrypt (Recommended)

```bash
# Install Nginx and Certbot
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/silentcamtrap
```

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # File upload size
        client_max_body_size 50M;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/silentcamtrap /etc/nginx/sites-enabled/

# Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

### Using Cloudflare

1. Add domain to Cloudflare
2. Point A record to server IP
3. Enable "Full (strict)" SSL mode
4. Enable "Always Use HTTPS"

---

## Domain Configuration

### DNS Records

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_SERVER_IP | 3600 |
| A | www | YOUR_SERVER_IP | 3600 |

### Update Python Client

After deployment, update the `config.json`:

```json
{
  "api_url": "https://your-domain.com/api/upload",
  ...
}
```

---

## Monitoring & Maintenance

### Docker Container Monitoring

```bash
# View container stats
docker stats silentcamtrap-server

# View logs
docker compose logs -f --tail=100

# Check health
curl http://localhost:3000/api/health
```

### Backup Strategy

```bash
# Backup data volumes
docker run --rm -v silentcamtrap_uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads-backup.tar.gz /data

# Scheduled backup (add to crontab)
0 2 * * * /path/to/backup-script.sh
```

### Updates

```bash
# Pull latest changes
cd SilentCamTrap
git pull

# Rebuild and restart
cd server
docker compose build
docker compose up -d
```

### Log Rotation

Docker handles log rotation automatically with the configuration in `docker-compose.yml`:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## Troubleshooting

### Container won't start
```bash
# Check logs
docker compose logs

# Check if port is in use
sudo lsof -i :3000
```

### Permission issues
```bash
# Fix data directory permissions
sudo chown -R 1001:1001 ./data
```

### Memory issues
```bash
# Increase Docker memory limit
docker update --memory="2g" silentcamtrap-server
```

---

## Security Checklist

- [ ] Changed default admin credentials
- [ ] Generated strong SESSION_SECRET
- [ ] Generated strong API_KEY
- [ ] SSL/HTTPS enabled
- [ ] Firewall configured
- [ ] Rate limiting enabled
- [ ] Regular backups scheduled
- [ ] Log monitoring setup

---

**Need help?** dev@devplus.fun
