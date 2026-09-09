# 🚀 Deployment Guide

Deploying the SilentCamTrap **server** for real use: Docker, VPS, reverse proxy, persistent
storage, backup, and hardening.

> **Before you start:** captured images and system/network metadata are personal data.
> Deploy only where you have written authorisation and a lawful basis, keep the dashboard off
> the public internet where possible, and decide a retention period up front.
> See the [README legal section](../README.md#legal-and-acceptable-use).

---

## Table of Contents

1. [Server requirements](#server-requirements)
2. [Pre-flight checklist](#pre-flight-checklist)
3. [Deployment options](#deployment-options)
4. [Docker deployment](#docker-deployment)
5. [VPS deployment without Docker](#vps-deployment-without-docker)
6. [Cloud platforms](#cloud-platforms)
7. [HTTPS and reverse proxy](#https-and-reverse-proxy)
8. [Domain and DNS](#domain-and-dns)
9. [Persistent data, backup and restore](#persistent-data-backup-and-restore)
10. [Monitoring and maintenance](#monitoring-and-maintenance)
11. [Hardening checklist](#hardening-checklist)
12. [Troubleshooting](#troubleshooting)

---

## Server requirements

### Minimum

| Resource | Specification |
|----------|---------------|
| CPU | 1 vCPU |
| RAM | 1 GB |
| Storage | 10 GB SSD |
| OS | Ubuntu 22.04 LTS / Debian 12 (20.04+ / 11+ work) |

### Recommended

| Resource | Specification |
|----------|---------------|
| CPU | 2 vCPUs |
| RAM | 2 GB |
| Storage | 50 GB SSD, sized against capture volume |
| OS | Ubuntu 22.04 LTS |

### Software

- **Docker Engine 20.10+ with the Compose v2 plugin** — *or* —
- **Node.js 18+ (20 LTS recommended) and npm 9+**. The container image is built on `node:20-alpine`.

Storage sizing: each capture is a ~100–400 KB JPEG (capped at `MAX_FILE_SIZE_MB`, default 10 MB)
plus a record in `intruder_data.json`. Expect roughly 0.3–0.5 GB per 1,000 captures. The
datastore is a single JSON array rewritten in full on every write, so keep entry counts modest
(or delete what you don't need).

---

## Pre-flight checklist

```bash
# Generate the secrets you will paste into server/.env
openssl rand -hex 32      # SESSION_SECRET
openssl rand -hex 16      # API_KEY
openssl rand -base64 18   # ADMIN_PASSWORD
```

Four values must **never** keep their defaults in a deployment: `SESSION_SECRET`, `API_KEY`,
`ADMIN_PASSWORD`, and `NODE_ENV`. `ADMIN_USERNAME` too. Also note that `.env` is the only place
these live — it is git-ignored, so back it up separately (losing it means a matching
`api_key` change on every client).

---

## Deployment options

| Option | Best for | Caveats |
|--------|----------|---------|
| **1. Docker Compose** ⭐ | Most deployments, easy upgrades | Compose forwards only a subset of env vars (see below) |
| **2. Direct Node.js + PM2** | Minimal resource use, custom systemd-ish control | You own Node updates and restarts |
| **3. Cloud PaaS** | Managed TLS, zero ops | **Ephemeral filesystem** — see the warning in [Cloud platforms](#cloud-platforms) |
| 4. Container service (ECS/Cloud Run) | Autoscaling | Needs a persistent volume and a single instance for session/datastore sanity |

A note on scale that is easy to miss: sessions use express-session's default **MemoryStore** and
the datastore is a **local JSON file**. The deployment is therefore single-process,
single-node by design; multiple replicas will each see their own data and their own sessions.

---

## Docker deployment

### Step 1: Prepare the host

```bash
sudo apt update && sudo apt upgrade -y

# Docker Engine + Compose v2 plugin (the convenience script installs both)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker            # or re-login

docker --version
docker compose version   # v2 subcommand; `docker-compose` only exists if v1 was installed
```

The get.docker.com script already provides `docker-compose-plugin`. Installing it again with
`apt install docker-compose-plugin` only works once the Docker apt repository exists, so skip
that step unless you added the repo yourself.

```bash
# Firewall: SSH first, always
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Only open `3000/tcp` if you deliberately have no reverse proxy — and then make sure TLS
considerations below still get solved, because login will not work over plain HTTP with
`NODE_ENV=production`.

### Step 2: Clone

```bash
git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git /opt/SilentCamTrap
cd /opt/SilentCamTrap/server
```

> The commands below assume the repository lives at `/opt/SilentCamTrap` (a system-owned path
> works better with PM2, backup scripts, and logrotate). Adjust the paths if you cloned into
> your home directory instead.

### Step 3: Configure the environment

```bash
cp .env.example .env
nano .env
```

```env
NODE_ENV=production
PORT=3000
SESSION_SECRET=<openssl rand -hex 32>
API_KEY=<openssl rand -hex 16>
ADMIN_USERNAME=<not admin>
ADMIN_PASSWORD=<openssl rand -base64 18>
ENABLE_AUTH=true
ENABLE_RATE_LIMIT=true
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
MAX_FILE_SIZE_MB=10
# WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>
```

### Step 4: Deploy with Docker Compose

```bash
docker compose up -d      # build + start
docker compose ps         # "healthy" after ~30s (healthcheck polls /api/health)
docker compose logs -f
```

`server/docker-compose.yml` creates container `silentcamtrap-server`, maps
`${PORT:-3000}:3000`, and mounts named volumes `silentcamtrap_uploads` and `silentcamtrap_logs`.

**What actually reaches the container** — Compose's `environment:` block only forwards these:

| Variable | Source |
|----------|--------|
| `SESSION_SECRET`, `API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | interpolated from `.env`, with placeholder fallbacks |
| `NODE_ENV=production`, `PORT=3000`, `ENABLE_AUTH=true`, `ENABLE_RATE_LIMIT=true`, `MAX_FILE_SIZE_MB=10` | **hardcoded** in the Compose file |
| `UPLOAD_DIR=/app/data/uploads`, `LOGS_DIR=/app/data/logs` | set as `ENV` in the Dockerfile (matches the volume mounts) |
| `WEBHOOK_URL`, `RATE_LIMIT_WINDOW_MS`, `RATE_LIMIT_MAX_REQUESTS`, `SESSION` cookie tuning | **not forwarded** — set in `.env` alone has no effect |

To use the un-forwarded ones, add them to `docker-compose.yml`:

```yaml
    environment:
      - WEBHOOK_URL=${WEBHOOK_URL:-}
      - RATE_LIMIT_WINDOW_MS=${RATE_LIMIT_WINDOW_MS:-900000}
      - RATE_LIMIT_MAX_REQUESTS=${RATE_LIMIT_MAX_REQUESTS:-100}
```

…then `docker compose up -d --build`. Also note the hardcoded `NODE_ENV=production` inside the
container: with `ENABLE_AUTH` on, session cookies are flagged `secure`, so **plain HTTP access to
`http://<ip>:3000` will bounce every login back to `/login`**. Put TLS in front (next section).

For development-in-Docker, override rather than editing the file:

```yaml
# docker-compose.override.yml
services:
  silentcamtrap:
    environment:
      - NODE_ENV=development
      - ENABLE_RATE_LIMIT=false
```

### Step 5: Verify

```bash
curl -s http://localhost:3000/api/health
# {"status":"healthy","uptime":12.34,"timestamp":"..."}
```

### Bind-mount alternative (simpler backups)

```bash
mkdir -p ./data/uploads ./data/logs
sudo chown -R 1001:1001 ./data          # image runs as uid/gid 1001 (nodeuser)
docker run -d \
  --name silentcamtrap-server \
  -p 127.0.0.1:3000:3000 \
  -v "$(pwd)/data:/app/data" \
  --env-file .env \
  silentcamtrap-server
```

Binding to `127.0.0.1` keeps the port off the public interface while Nginx does the TLS work.
`--env-file` passes every key in `.env`, which is broader than what Compose forwards.

---

## VPS deployment without Docker

```bash
# Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version && npm --version

sudo npm install -g pm2

git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git
cd SilentCamTrap/server
npm ci --omit=dev          # `--only=production` was deprecated in npm 8; use --omit=dev

cp .env.example .env && nano .env
```

`dotenv` loads `.env` from the **process working directory**, so the app must be started from
`server/`:

```bash
pm2 start src/server.js --name silentcamtrap --cwd "$PWD"
pm2 save
pm2 startup systemd        # follow the printed command
```

Equivalent ecosystem file (keeps cwd and env explicit):

```js
// server/ecosystem.config.js
module.exports = {
  apps: [{
    name: 'silentcamtrap',
    script: 'src/server.js',
    cwd: __dirname,
    instances: 1,            // MemoryStore sessions + JSON file datastore => one instance
    autorestart: true,
    max_memory_restart: '400M',
    env_production: { NODE_ENV: 'production', PORT: 3000 },
  }],
};
```

```bash
pm2 start ecosystem.config.js --env production
pm2 logs silentcamtrap
```

Do **not** set `instances: max` / cluster mode: each worker would keep its own in-memory session
store and race on `intruder_data.json`.

---

## Cloud platforms

> ⚠️ **Ephemeral filesystem warning.** Captured images go to `UPLOAD_DIR` and the entire
> dashboard datastore is `<LOGS_DIR>/intruder_data.json` on local disk. On Heroku, Render,
> Fly.io without volumes, App Platform without a mounted volume, or Cloud Run, that directory is
> wiped on every restart/redeploy — silently losing captures. Prefer a droplet/EC2/Lightsail with
> a real disk, or mount a persistent volume before pointing clients at it.

### DigitalOcean App Platform

1. Fork/point the app at this repository, **root directory `server/`**.
2. Build command `npm ci`; run command `npm start`; health check path `/api/health`.
3. Set env vars in the UI (`SESSION_SECRET`, `API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`).
4. Attach a persistent volume mounted at `/app/data` if your plan supports it — otherwise use a
   Droplet instead and follow the Docker section.

### AWS EC2

1. Launch a t3.small (2 vCPU / 2 GB is more comfortable) with Ubuntu 22.04 and a ≥ 20 GB gp3 volume.
2. Security group: allow 22 from your IP, 80/443 from anywhere. **Do not** open 3000 — the app
   listens on loopback behind Nginx.
3. Follow [Docker deployment](#docker-deployment) or [VPS deployment without Docker](#vps-deployment-without-docker).
4. Snapshot the EBS volume as your backup mechanism, plus the file-level backups below.

### Heroku (reference only)

The free tier no longer exists and dyno disks are ephemeral, so captures will not survive a
restart. If you still use it:

```bash
heroku create silentcamtrap
heroku config:set NODE_ENV=production SESSION_SECRET=... API_KEY=... ADMIN_PASSWORD=...
heroku buildpacks:set heroku/nodejs
# Deploy the server/ subtree only:
git subtree push --prefix server heroku main
```

---

## HTTPS and reverse proxy

TLS is not optional here for two reasons: the `secure` session cookie in production (login will
loop without HTTPS), and because captures traverse the network.

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo nano /etc/nginx/sites-available/silentcamtrap
```

```nginx
# Throttle /login: the app's rate limiter only covers /api/*
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

server {
    listen 80;
    server_name camtrap.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name camtrap.example.com;

    ssl_certificate     /etc/letsencrypt/live/camtrap.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/camtrap.example.com/privkey.pem;

    # Must be >= MAX_FILE_SIZE_MB (default 10) or Nginx rejects uploads with 413
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Uploaded images are served with NO auth by the app — protect them here,
    # or delete this block and deny the path entirely.
    location /uploads/ {
        auth_basic           "SilentCamTrap";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        add_header Cache-Control "private, max-age=3600";
    }

    location /login {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Belt and braces: never expose the raw app port even if the firewall slips
    location /api/health {
        proxy_pass http://127.0.0.1:3000;
        access_log off;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/silentcamtrap /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Rate limiting is per proxy IP: trust X-Forwarded-For by keeping proxy_set_header as above,
# and remember express's limiter counts per client IP as seen by the app.
sudo certbot --nginx -d camtrap.example.com
sudo certbot renew --dry-run
```

Alternative: **Cloudflare** in front (DNS → proxy orange-cloud, SSL mode *Full (strict)*,
*Always Use HTTPS*). Note Cloudflare's free-tier upload limit is 100 MB (fine) but HTML caching
can serve a stale dashboard — cache-rule `/api/*` and `/login` as bypass.

If clients sit behind corporate TLS inspection, `requests` may fail verification; fix it on the
client network side rather than disabling certificate verification in the code.

---

## Domain and DNS

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` | `<server IPv4>` | 3600 |
| A | `camtrap` | `<server IPv4>` | 3600 |
| AAAA | `camtrap` | `<server IPv6>` | 3600 |

Then point clients at the HTTPS origin in `python/config.json`:

```json
{ "api_url": "https://camtrap.example.com/api/upload" }
```

`api_key` must match the server's `API_KEY`. Rebuild or redeploy `config.json` after changing it —
frozen executables read it from the working directory, not from inside the bundle
([BUILD.md](BUILD.md#runtime-paths-you-must-get-right)).

---

## Persistent data, backup and restore

Two directories matter, and **both** must be backed up:

| Contents | Path in container | Named volume |
|----------|-------------------|--------------|
| Captured images (`YYYY-MM-DD/uuid.jpg`) | `/app/data/uploads` | `silentcamtrap_uploads` |
| `access.log` **and `intruder_data.json` — the entire datastore** | `/app/data/logs` | `silentcamtrap_logs` |

Losing the logs volume loses every captured entry, even if the images survive.

### Backup

```bash
#!/usr/bin/env bash
# /usr/local/sbin/silentcamtrap-backup.sh
set -euo pipefail
STAMP=$(date -u +%F_%H%M)
DEST=/var/backups/silentcamtrap
mkdir -p "$DEST"

# Pause writes for a consistent JSON snapshot (the file is rewritten whole, not atomically)
docker compose -f /opt/SilentCamTrap/server/docker-compose.yml stop silentcamtrap

docker run --rm -v silentcamtrap_uploads:/d -v "$DEST":/backup alpine \
  tar czf "/backup/uploads-$STAMP.tar.gz" -C /d .
docker run --rm -v silentcamtrap_logs:/d -v "$DEST":/backup alpine \
  tar czf "/backup/data-$STAMP.tar.gz" -C /d .

docker compose -f /opt/SilentCamTrap/server/docker-compose.yml up -d
find "$DEST" -name '*.tar.gz' -mtime +30 -delete
```

```bash
sudo chmod 700 /usr/local/sbin/silentcamtrap-backup.sh
# Nightly, and keep the archive encrypted off-box
( crontab -l 2>/dev/null; echo '15 2 * * * /usr/local/sbin/silentcamtrap-backup.sh >> /var/log/silentcamtrap-backup.log 2>&1' ) | crontab -
gpg --symmetric --cipher-algo AES256 /var/backups/silentcamtrap/data-2026-09-09_0215.tar.gz
```

For PM2 installs, replace the docker run lines with `tar czf "$DEST/data-$STAMP.tar.gz" -C /opt/SilentCamTrap/server/data .`
and stop the app briefly with `pm2 stop silentcamtrap`.

### Restore

```bash
docker compose down
docker run --rm -v silentcamtrap_uploads:/d -v /var/backups/silentcamtrap:/backup:ro alpine \
  tar xzf /backup/uploads-2026-09-09_0215.tar.gz -C /d
docker run --rm -v silentcamtrap_logs:/d -v /var/backups/silentcamtrap:/backup:ro alpine \
  tar xzf /backup/data-2026-09-09_0215.tar.gz -C /d
sudo chown -R 1001:1001 $(docker volume inspect -f '{{.Mountpoint}}' silentcamtrap_logs) \
               $(docker volume inspect -f '{{.Mountpoint}}' silentcamtrap_uploads)
docker compose up -d
```

Verify with `GET /api/stats` (in a browser session) or by loading `/entries`.

### Retention & pruning

Images accumulate indefinitely — nothing in the app deletes them. Prefer the API so entries and
files stay in sync:

```bash
# list then delete (requires a dashboard session cookie)
curl -s -b cookies.txt 'http://localhost:3000/api/entries?limit=1000' | jq -r '.data[].id'
curl -s -b cookies.txt -X DELETE "http://localhost:3000/api/entries/<id>"
```

Bulk filesystem cleanup of date folders older than N days (leaves stale JSON rows whose thumbnails
will render as "N/A"):

```bash
find /app/data/uploads -mindepth 1 -maxdepth 1 -type d -mtime +90 -print   # review first
```

### Access log growth

`data/logs/access.log` receives a Morgan `combined` line per request and is **not** rotated by
Docker (only container stdout is). Add a logrotate rule:

```
/opt/SilentCamTrap/server/data/logs/access.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
```

---

## Monitoring and maintenance

```bash
docker compose ps                        # status + health
docker stats silentcamtrap-server --no-stream
docker compose logs -f --tail=100

# From the host
curl -s http://localhost:3000/api/health | jq .

# Watch for unexpected client activity / errors
sudo tail -f /opt/SilentCamTrap/server/data/logs/access.log | grep -vE ' 200 '
```

Useful uptime probe: `/api/health` returns `{status, uptime, timestamp}` and needs no auth, which
is why both the Dockerfile and Compose use it.

### Updates

```bash
cd /opt/SilentCamTrap && git fetch --tags && git pull
cd server
docker compose build --pull && docker compose up -d   # rebuild image, keep volumes
# PM2 installs:
npm ci --omit=dev && pm2 reload silentcamtrap
```

Expect a restart to log the dashboard out (in-memory sessions). After a schema/config change,
confirm `GET /api/health` and one end-to-end test capture before considering the deploy done.

---

## Hardening checklist

- [ ] `ADMIN_USERNAME`/`ADMIN_PASSWORD` changed; no `admin123`
- [ ] `SESSION_SECRET` and `API_KEY` regenerated (`openssl rand -hex …`), `default-api-key` gone
- [ ] `NODE_ENV=production`, `ENABLE_AUTH=true`, `ENABLE_RATE_LIMIT=true`
- [ ] TLS valid and auto-renewing; HTTP redirects to HTTPS
- [ ] App port bound to `127.0.0.1` or firewalled — **not** publicly reachable on `:3000`
- [ ] `/uploads` behind `auth_basic`/IP allow-list (or denied) — the app serves it unauthenticated
- [ ] `/login` throttled at the proxy (the app limits only `/api/*`)
- [ ] `client_max_body_size` ≥ `MAX_FILE_SIZE_MB`
- [ ] `.env` mode `600`, owned by the deploying user, backed up out-of-band
- [ ] Both volumes backed up nightly; archives encrypted; restore tested once
- [ ] Logrotate for `access.log`; retention policy defined for captures
- [ ] Single instance only (MemoryStore sessions + one JSON datastore)
- [ ] `npm audit --audit-level=high` reviewed periodically (it runs, non-blocking, in CI)
- [ ] Written authorisation, notice/consent, and a deletion-on-request process documented
- [ ] Server time syncs (`timedatectl`) — datastore timestamps and the "today/this week" stats depend on it

---

## Troubleshooting

### Container restarts / unhealthy
```bash
docker compose logs --tail=100
sudo lsof -i :3000                      # host port already taken?
docker inspect -f '{{json .State.Health}}' silentcamtrap-server | jq
```

### Permission denied writing data
The image runs as uid/gid `1001`. For bind mounts:
```bash
sudo chown -R 1001:1001 ./data
```
Named volumes inherit ownership from the image build, so this is only needed for bind mounts.

### Login redirects back to `/login` forever
`NODE_ENV=production` sets `cookie.secure = true`, so the browser drops the session cookie on
plain HTTP. Use HTTPS, or test with `NODE_ENV=development`.

### Client gets 401
`api_key` in `config.json` must equal the container's `API_KEY`. Note Compose overrides an unset
value with `your-secure-api-key`, not with your `.env`'s value if the file is not where Compose
looks (it reads `.env` in the Compose project directory, i.e. `server/`).

### Client gets 429
Rate limit is per IP across all `/api/*` — many clients behind one NAT address share
100 requests / 15 min. Raise `RATE_LIMIT_MAX_REQUESTS` (and forward it in Compose) or spread clients out.

### Nginx 413 on upload
`client_max_body_size` is below `MAX_FILE_SIZE_MB`; raise it and `sudo systemctl reload nginx`.

### Dashboard shows rows but no thumbnails
The image file is missing from `UPLOAD_DIR` (volume remounted, folder renamed, or entries deleted
by hand). The detail view falls back to an "N/A" placeholder. Restore the uploads volume.

### Memory grows over time
The whole datastore is held in memory. Prune old entries, then restart.

---

**Questions or bugs?** open an issue:
<https://github.com/mahmud-r-farhan/SilentCamTrap/issues>
