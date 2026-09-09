# 🔒 SilentCamTrap

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Node](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen.svg)
![Python](https://img.shields.io/badge/python-%3E%3D3.8-blue.svg)
![CI](https://img.shields.io/badge/CI-lint%20%26%20validate-informational.svg)

**Intruder Detection & Capture Review System**

*Capture an event, collect the surrounding context, review it in a dashboard*

[Features](#features) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Documentation](#documentation) • [API Reference](#api-reference)

</div>

---

## ⚖️ Read this first

SilentCamTrap can capture webcam images and read local system data, so it touches
privacy law in almost every jurisdiction. Use it **only** on machines you own or are
explicitly authorised to monitor, and where the people involved have notice and
consent.

- `enable_shutdown` and `enable_self_delete` ship **disabled by default** and are
  intended for controlled lab demos, not production endpoints.
- Do not deploy the client on third-party or managed devices without written authorisation.
- Unauthorised access to a computer, or intercepting data from a network or communications
  service, is illegal in many countries (for example the US CFAA, the UK Computer Misuse Act,
  the EU GDPR for personal data handling).

The repository author is not responsible for misuse. See [LICENSE](LICENSE) and
[Legal and acceptable use](#legal-and-acceptable-use).

---

## 📋 Overview

SilentCamTrap is a two-part system:

1. A **Python client** that, when executed on a machine, grabs a webcam frame plus
   local system/network context and POSTs it to a server.
2. A **Node.js server** that stores each capture on disk and serves an EJS dashboard
   for reviewing, mapping, exporting, and deleting the entries.

### What's Included

| Component | Path | Description |
|-----------|------|-------------|
| Python client | `python/` | Data-collection agent, packaged with PyInstaller |
| Node.js server | `server/` | Express API, JSON datastore, file uploads |
| Dashboard | `server/src/views/` | EJS templates with a dark theme and a Leaflet map |
| Container setup | `server/Dockerfile`, `server/docker-compose.yml` | Multi-stage image, non-root user, health check |

---

## Features

### 🐍 Python client (`python/client.py`)

- Webcam capture that grabs `webcam_frame_count` frames and keeps the **sharpest** one
  (Laplacian variance), targeting 1280×720 and saving JPEG at quality 95
- Network context: public IP (4 fallback lookup services), local IP, hostname, MAC address,
  current Wi-Fi SSID, and nearby SSIDs (Windows only, via `netsh`)
- Approximate geolocation from the public IP, with `geocoder` first and `ip-api.com` as fallback
- System inventory: OS/CPU/RAM/disk, battery, uptime, process count, screen resolution,
  locale, timezone, username, Python version (`psutil` used when installed, skipped when not)
- Browser history: last `max_browser_history` entries from Chrome, Edge (Windows), and Firefox,
  read from a temporary copy of the profile database so a running browser is not locked
- Upload with retry and exponential backoff (`send_retries`, `send_retry_delay`)
- Structured logging to `<log_folder>/client.log`
- Optional post-upload actions, both **off by default**: `enable_shutdown`, `enable_self_delete`
- Single-shot execution: runs once, exits `0` on success, `1` on failure (no scheduler built in)

### 🚀 Node.js server (`server/src/server.js`)

- Express + EJS, Helmet CSP, compression, CORS, Morgan access logging
- Two independent auth mechanisms: session cookie for the dashboard, `X-API-KEY` for client uploads
- Multer disk storage: images only, size-capped, stored in date-folders (`uploads/YYYY-MM-DD/`)
- JSON file datastore (`data/logs/intruder_data.json`) with add / list / get / delete
- CSV and JSON export endpoints
- Optional webhook alert (`WEBHOOK_URL`) fired on every new capture
- Health endpoint used by the Docker `HEALTHCHECK`

### 🎨 Dashboard (`/`)

- Dark theme with glassmorphism cards, responsive layout, collapsible sidebar
- Stat cards: total captures, today, this week, distinct countries
- Recent-captures table with thumbnails and a small Leaflet map of recent locations
- Entries list with thumbnails, server-side pagination (20 per page) and CSV/JSON export buttons
- Entry detail view: image, network, geolocation, system, and per-browser history columns
- Map view of the last 100 captures with coordinates
- Settings view showing the effective auth / rate-limit / upload-size configuration
- Delete with confirmation (deletes the record and its image file)

> **Accurate expectations:** the dashboard is **server-rendered, not live**. There is no
> chart library and no WebSocket/polling — statistics refresh when you reload the page.
> The entries list is paginated but has **no search or filter UI**; the export endpoints
> are the way to slice data offline.

---

## Quick Start

### Prerequisites

- **Node.js** v18.0.0 or higher (`engines` in `server/package.json`; CI uses v20)
- **Python** 3.8 or higher (CI and the release build use 3.11)
- **npm** — `server/package-lock.json` is the only lockfile in the repo, so
  `npm ci` works; there is no `yarn.lock`, so `yarn` will ignore pinned versions
- **Docker Engine 20.10+ with the Compose v2 plugin** (optional)
- FFmpeg-free: OpenCV provides the webcam backend, no extra system package needed on Windows/macOS

### Clone and run the server

```bash
git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git
cd SilentCamTrap/server

npm install            # or `npm ci` to honour package-lock.json
cp .env.example .env   # then edit .env — defaults are insecure on purpose
npm run dev            # nodemon; use `npm start` for plain node
```

The server creates `server/data/uploads/` and `server/data/logs/` on first start
(both are git-ignored). Dashboard: `http://localhost:3000`, login `admin` / `admin123`.

Windows and macOS/Linux users can alternatively run `server\start.bat` or `./server/start.sh`,
which check for Node, install dependencies, copy `.env.example` to `.env`, and start the server.

### Set up and run the client

```bash
cd ../python
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# edit config.json: api_url must point at your server, api_key must match server API_KEY
python client.py
```

Then check the dashboard: the capture appears in *Recent Captures* and on `/entries`.

---

## Configuration

### Server environment variables (`server/.env`)

| Variable | Default (if unset) | Effect |
|----------|--------------------|--------|
| `NODE_ENV` | `development` | `production` sets `secure: true` on session cookies (see [HTTPS requirement](#security-considerations)) |
| `PORT` | `3000` | HTTP listen port |
| `SESSION_SECRET` | `change-me-in-production` | express-session signing key — set a long random value |
| `API_KEY` | `default-api-key` | Must match `api_key` in `python/config.json` |
| `ADMIN_USERNAME` | `admin` | Dashboard login user |
| `ADMIN_PASSWORD` | `admin123` | Dashboard login password |
| `RATE_LIMIT_WINDOW_MS` | `900000` (15 min) | Rate-limit window, applied to `/api/*` only |
| `RATE_LIMIT_MAX_REQUESTS` | `100` | Requests per window per IP (429 above it) |
| `MAX_FILE_SIZE_MB` | `10` | Per-file upload cap enforced by Multer |
| `UPLOAD_DIR` | `<server>/data/uploads` | Image storage root, also served at `/uploads` |
| `LOGS_DIR` | `<server>/data/logs` | Access log **and** `intruder_data.json` (the datastore) |
| `ENABLE_AUTH` | `true` (disabled only by `false`) | `false` bypasses **both** session and API-key checks — development only |
| `ENABLE_RATE_LIMIT` | `true` (disabled only by `false`) | Toggles the limiter |
| `WEBHOOK_URL` | *empty* (off) | `POST`s a JSON `new_capture` alert per upload; works with Discord/Slack-style webhooks and custom endpoints |

Generate strong values with `openssl rand -hex 32` (secret) and `openssl rand -hex 16` (API key).

### Client configuration (`python/config.json`)

```json
{
  "api_url": "http://localhost:3000/api/upload",
  "api_key": "default-api-key",
  "log_folder": "intruder_logs",
  "webcam_index": 0,
  "webcam_warmup_seconds": 0.8,
  "webcam_frame_count": 10,
  "connection_timeout": 30,
  "send_retries": 3,
  "send_retry_delay": 2.0,
  "collection_timeout": 20,
  "enable_shutdown": false,
  "enable_self_delete": false,
  "enable_browser_history": true,
  "max_browser_history": 10,
  "log_level": "INFO"
}
```

| Key | Type / default | Meaning |
|-----|----------------|---------|
| `api_url` | string / `http://localhost:3000/api/upload` | Full URL of the upload endpoint |
| `api_key` | string / `default-api-key` | Sent as the `X-API-KEY` header |
| `log_folder` | string / `intruder_logs` | Output directory for the JPEG and `client.log`; created if missing, resolved **relative to the current working directory** |
| `webcam_index` | int / `0` | OpenCV camera index — try `1` or `2` if nothing is captured |
| `webcam_warmup_seconds` | float / `0.8` | Exposure warm-up before frames are read |
| `webcam_frame_count` | int / `10` | Candidate frames captured; the sharpest is kept |
| `connection_timeout` | int / `30` | Seconds; used for both the public-IP lookups and the upload request |
| `send_retries` | int / `3` | Upload attempts before giving up |
| `send_retry_delay` | float / `2.0` | Initial back-off; it doubles each retry |
| `collection_timeout` | int / `20` | Max seconds to wait for the parallel collectors; partial data is sent on timeout |
| `enable_browser_history` | bool / `true` | Turn history collection off to skip it entirely |
| `max_browser_history` | int / `10` | Rows per browser |
| `enable_shutdown` | bool / `false` | **Destructive.** `shutdown /s /t 5` (Windows) or `shutdown -h +1` |
| `enable_self_delete` | bool / `false` | **Destructive.** Schedules deletion of the running script/exe |
| `log_level` | string / `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Only these keys are recognised — `Config.from_file()` ignores anything else, so keys such as
`chrome_path` or `firefox_path` (seen in older docs) are silently no-ops. Browser database
locations are hardcoded per operating system; see [docs/BUILD.md](docs/BUILD.md#browser-history-paths).

Environment overrides (applied after `config.json`):

| Variable | Overrides | Accepted value |
|----------|-----------|----------------|
| `SILENTCAMTRAP_API_URL` | `api_url` | any string |
| `SILENTCAMTRAP_API_KEY` | `api_key` | any string |
| `SILENTCAMTRAP_ENABLE_SHUTDOWN` | `enable_shutdown` | `true` enables; anything else disables |
| `SILENTCAMTRAP_ENABLE_DELETE` | `enable_self_delete` | `true` enables; anything else disables |

---

## 🐳 Docker deployment

```bash
cd server
cp .env.example .env    # Compose interpolates SESSION_SECRET, API_KEY, ADMIN_* from this file
docker compose up -d    # Compose v2 plugin; `docker-compose` also works if you have v1
docker compose logs -f
docker compose ps       # healthcheck polls /api/health every 30s
docker compose down     # keeps the named volumes
```

Plain `docker` CLI:

```bash
cd server
docker build -t silentcamtrap-server .
docker run -d \
  --name silentcamtrap-server \
  -p 3000:3000 \
  -v "$(pwd)/data:/app/data" \
  -e SESSION_SECRET="$(openssl rand -hex 32)" \
  -e API_KEY="$(openssl rand -hex 16)" \
  -e ADMIN_PASSWORD="$(openssl rand -base64 18)" \
  silentcamtrap-server
```

The image runs as uid/gid `1001` with `/app/data` as the writable mount point. Compose only
forwards a subset of variables into the container — see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#step-4-deploy-with-docker-compose) for the full list and
for how to pass the rest.

---

## API Reference

### Authentication model

| Surface | Mechanism | Notes |
|---------|-----------|-------|
| `POST /api/upload` (and legacy `/upload`) | `X-API-KEY` header, or `?apiKey=` query parameter | Header name is read case-insensitively; query param is convenient for `curl`/`wget` smoke tests |
| Dashboard pages (`/`, `/entries`, `/entry/:id`, `/map`, `/settings`) | Session cookie | Unauthenticated browsers are **302-redirected** to `/login` |
| `GET /api/entries`, `/api/entries/:id`, `/api/stats`, `/api/export/csv`, `/api/export/json`, `DELETE /api/entries/:id` | Session cookie only | An API key is **not** accepted here; a request without `Accept: application/json` gets a 302 to `/login`, with it a 401 JSON error |
| `GET /api/health` | none | Used by the container health check |
| `GET /uploads/*` | none | Uploaded images are served statically — see [Security considerations](#security-considerations) |

Setting `ENABLE_AUTH=false` bypasses every check above. Never run that in production.

### Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/upload` | API key | Receive `file` + `data` multipart fields, store the entry |
| `POST` | `/upload` | API key | Legacy alias; returns `text/plain` instead of JSON |
| `GET` | `/api/entries?limit=&offset=` | session | Paged entries (`limit` default 100) |
| `GET` | `/api/entries/:id` | session | Single entry |
| `DELETE` | `/api/entries/:id` | session | Delete entry **and** its image file |
| `GET` | `/api/stats` | session | Totals, today, this week, countries, recent coordinates |
| `GET` | `/api/export/csv` | session | Flattened CSV of up to 10,000 entries (Excel-friendly, BOM-prefixed) |
| `GET` | `/api/export/json` | session | Full JSON dump of up to 10,000 entries |
| `GET` | `/api/health` | none | `{status, uptime, timestamp}` |
| `GET`/`POST` | `/login`, `GET /logout` | none | Session lifecycle |

#### `POST /api/upload`

```bash
curl -X POST http://localhost:3000/api/upload \
  -H "X-API-KEY: default-api-key" \
  -F "file=@capture.jpg;type=image/jpeg" \
  -F "data=@capture.json;type=application/json"
```

```json
{ "success": true, "message": "Data uploaded successfully", "id": "8f772b3f-83f1-46eb-b930-ebaa15323122" }
```

Both fields are `multipart/form-data`: `file` (an `image/*` MIME type, required) and `data`
(`application/json`, optional; any other MIME type is rejected). The server generates the
entry `id` and timestamp, moves the image to `<UPLOAD_DIR>/YYYY-MM-DD/<uuid>.<ext>`, and the
`data` blob is stored verbatim under `extraData` — so new client fields appear in the datastore
without a server change.

#### `GET /api/entries`

```json
{ "success": true, "data": [ /* entries */ ], "total": 2, "limit": 100, "offset": 0 }
```

Each entry: `{ id, timestamp, imagePath, imageFilename, extraData, clientIp }`.

#### Error responses

| Status | Body | Cause |
|--------|------|-------|
| `400` | `{"error":"No image uploaded"}` | Missing `file` field |
| `400` | `{"error":"Upload error: ..."}` | Multer rejection: wrong MIME type, or `File too large` (`MAX_FILE_SIZE_MB`) |
| `401` | `{"error":"Invalid API key"}` | Missing/wrong key on an upload route |
| `401` | `{"error":"Authentication required"}` | Missing session on a JSON request |
| `404` | `{"error":"Entry not found"}` | Unknown `:id` |
| `429` | `{"error":"Too many requests, please try again later."}` | More than `RATE_LIMIT_MAX_REQUESTS` per window on `/api/*` |
| `500` | `{"error":"Upload failed"}` | Unexpected server-side failure |

---

## 🗂 Data & storage layout

```
server/data/                     # created at runtime, git-ignored
├── uploads/
│   └── 2026-09-09/              # one folder per UTC day
│       └── <uuid>.jpg           # served at GET /uploads/2026-09-09/<uuid>.jpg
└── logs/
    ├── access.log               # Morgan "combined" stream
    └── intruder_data.json       # ← the entire dashboard datastore
```

`intruder_data.json` is a plain pretty-printed JSON array, rewritten on every write. It is the
only place entry metadata lives: **back it up**, and do not edit it while the server is running.
Images on disk whose entry is deleted via the dashboard or `DELETE /api/entries/:id` are removed
with it; entries deleted from the JSON by hand leave orphan files behind.

---

## 📁 Project structure

```
SilentCamTrap/
├── python/
│   ├── client.py            # collection agent
│   ├── config.json          # client configuration (see table above)
│   ├── requirements.txt     # opencv-python, requests, geocoder, psutil, pyinstaller
│   ├── game.ico             # icon used by the PyInstaller build
│   ├── build.bat            # Windows build wrapper (runs: pyinstaller --clean silentcamtrap.spec)
│   └── build.sh             # Linux/macOS build wrapper (same spec file)
├── server/
│   ├── src/
│   │   ├── server.js        # single-file Express app: middleware, routes, datastore
│   │   ├── views/           # dashboard, entries, entry-detail, login, map, settings, error,
│   │   │                    # layout + partials/ (head, styles, scripts, header-bar, sidebar, footer)
│   │   └── public/css/       # main.css, entries.css, login.css, map.css
│   ├── data/                # created at runtime (uploads/, logs/)
│   ├── package.json         # scripts: start, dev, docker:build, docker:run, test
│   ├── Dockerfile           # multi-stage node:20-alpine, non-root uid 1001
│   ├── docker-compose.yml   # container name silentcamtrap-server, named volumes
│   ├── .env.example
│   ├── .dockerignore
│   ├── start.sh / start.bat # convenience launchers
├── docs/
│   ├── BUILD.md             # PyInstaller builds + troubleshooting
│   └── DEPLOYMENT.md        # Docker / VPS / reverse proxy / backups
├── .github/workflows/
│   ├── ci.yml               # flake8, JSON + .env.example validation, npm ci, node --check
│   └── build.yml            # Windows EXE on `v*` tags (see note in docs/BUILD.md)
├── .github/dependabot.yml
├── CODE_OF_CONDUCT.md
├── LICENSE                  # MIT + usage disclaimer
└── todo                     # roadmap (includes unimplemented, lab-only simulations)
```

There is no `tests/` directory: `npm test` and the Python CI job only lint and validate.

---

## Security considerations

Documented **as built**, so you can make an informed decision before exposing this anywhere:

1. **HTTPS is mandatory in production.** When `NODE_ENV=production` the session cookie is
   flagged `secure`, so signing in over plain `http://server-ip:3000` silently loops back to
   `/login`. Put Nginx/Caddy + Let's Encrypt in front.
2. **`/uploads` is public.** Static images are served with no auth. Anyone who learns a
   filename can fetch the image. Protect it at the proxy (`auth_basic`, IP allow-list) or
   keep the server on a private network — filenames are UUIDs, which is obscurity, not access control.
3. **`/login` is not rate-limited.** The limiter is mounted on `/api/` only, so credential
   guessing must be throttled at the reverse proxy (or with fail2ban).
4. **Credentials are compared as plaintext strings** from `.env`. `bcryptjs` is a declared
   dependency but is not used by the login handler, and there is no user store — one admin
   account, one password. Change it, and treat `.env` as a secret (it is git-ignored).
5. **Sessions use the default MemoryStore.** Restarting the server logs everyone out, and
   running more than one instance breaks auth. Use one process, or add a session store.
6. **CORS is closed in production** (`origin: false`), so third-party browser JS cannot call
   the API; the Python client is unaffected because it is not a browser.
7. **Rate limit covers `/api/*` per IP**, including your own clients. A fleet of clients behind
   one NAT IP shares the 100-per-15-minutes budget; raise `RATE_LIMIT_MAX_REQUESTS` or set
   `ENABLE_RATE_LIMIT=false` behind an authenticated proxy.
8. **Data retention.** Captures are personal data. Encrypt backups, set a retention period,
   and delete entries you no longer need through the API or dashboard.
9. `ENABLE_AUTH=false` and the default `API_KEY`/`admin123` values exist for local convenience
   only — verify none of them are set before you expose a port.

---

## 🧰 Development & CI

- `npm run dev` — nodemon (devDependency); `npm start` — plain node
- `npm run docker:build`, `npm run docker:run` — image build/run shortcuts
- `npm test` — placeholder; **no test suite exists yet**
- CI (`.github/workflows/ci.yml`) runs on every push/PR: flake8 on `client.py`
  (syntax/undefined-name errors are fatal, style issues are warnings), JSON validity for every
  config file, a check that `server/.env.example` contains the required keys, `npm ci`,
  and `node --check src/server.js`
- `build.yml` builds the Windows client on `v*` tags (or manually) and attaches a zip to the release

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/BUILD.md](docs/BUILD.md) | PyInstaller builds for Windows/Linux/macOS, spec file, browser-path reality, troubleshooting |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, VPS + PM2, reverse proxy/HTTPS, volumes, backup/restore, hardening checklist |
| [Wiki](https://github.com/mahmud-r-farhan/SilentCamTrap/wiki) | Longer-form notes |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards and the enforcement contact |

---

## 🤝 Support

- 🐛 **Issues:** [GitHub Issues](https://github.com/mahmud-r-farhan/SilentCamTrap/issues) —
  include the client log, server version, and (redacted) config
- 📧 **Code of conduct reports:** see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 👤 **Author:** [Mahmud Rahman](https://github.com/mahmud-r-farhan)

---

## 📄 License

MIT — see [LICENSE](LICENSE), which also contains the usage disclaimer below.

## Legal and acceptable use

This project is intended for education, authorised penetration testing, and protecting
systems you own. It is **not** sanctioned for:

- monitoring a person without their knowledge or consent;
- accessing computers, accounts, or networks you are not authorised to use;
- collecting, storing, or transferring personal data in breach of privacy law;
- use as surveillance in a workplace, school, household, or relationship where the
  people affected have not been informed.

Obtain written authorisation and legal advice before deploying, and comply with every
applicable local, national, and international law. You are solely responsible for your use
of this software.

---

<div align="center">

**Made with ❤️ by [Mahmud Rahman](https://github.com/mahmud-r-farhan)**

</div>
