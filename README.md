# 🔒 SilentCamTrap

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Node](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen.svg)
![Python](https://img.shields.io/badge/python-%3E%3D3.8-blue.svg)

**Advanced Intruder Detection & Data Collection System**

*Capture, analyze, and monitor security events with an elegant dashboard*

[Features](#-features) • [Installation](#-installation) • [Documentation](#-documentation) • [API](#-api-reference) • [Support](#-support)

</div>

---

## 📋 Overview

SilentCamTrap is a comprehensive security monitoring solution that captures intruder data including webcam images, system information, network details, and browser history. The system features a modern, interactive dashboard for viewing and managing captured data.

### What's Included

| Component | Description |
|-----------|-------------|
| **Python Client** | Cross-platform data collection agent |
| **Node.js Server** | RESTful API with persistent storage |
| **EJS Dashboard** | Interactive web interface with dark theme |
| **Docker Support** | Production-ready containerization |

---

## ✨ Features

### 🐍 Python Client
- ✅ Webcam image capture with quality optimization
- ✅ Cross-platform support (Windows, macOS, Linux)
- ✅ Multiple IP detection services with fallback
- ✅ Geolocation via IP address
- ✅ Browser history collection (Chrome, Firefox)
- ✅ System information gathering
- ✅ Configurable via JSON file or environment variables
- ✅ Professional logging with file output
- ✅ PyInstaller-ready for standalone executables

### 🚀 Node.js Server
- ✅ Express.js with security middleware (Helmet, CORS)
- ✅ Session-based authentication
- ✅ Rate limiting for API protection
- ✅ File upload with validation
- ✅ Persistent JSON-based data storage
- ✅ Health check endpoint
- ✅ Organized date-based file storage
- ✅ RESTful API design

### 🎨 Dashboard
- ✅ Stunning dark theme with glassmorphism
- ✅ Real-time statistics and charts
- ✅ Interactive Leaflet map visualization
- ✅ Responsive design (mobile-friendly)
- ✅ Entry detail view with all captured data
- ✅ Browser history viewer
- ✅ Pagination and filtering
- ✅ Export functionality

---

## 🚀 Installation

### Prerequisites

- **Node.js** v18.0.0 or higher
- **Python** 3.8 or higher
- **npm** or **yarn**
- **Docker** (optional, for containerized deployment)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/mahmud-r-farhan/SilentCamTrap.git
cd SilentCamTrap

# Install server dependencies
cd server
npm install

# Copy environment file and configure
cp .env.example .env
# Edit .env with your settings

# Start the server
npm run dev

# In another terminal, set up Python client
cd ../python
pip install -r requirements.txt
```

---

## 📖 Documentation

### Server Setup

#### 1. Environment Configuration

Create a `.env` file in the `server` directory:

```env
# Server Configuration
NODE_ENV=development
PORT=3000

# Security
SESSION_SECRET=your-super-secret-session-key-change-in-production
# API_KEY must match the api_key in python/config.json
API_KEY=default-api-key

# Admin Credentials (change these!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100

# File Upload
MAX_FILE_SIZE_MB=10
UPLOAD_DIR=./data/uploads
LOGS_DIR=./data/logs

# Features
ENABLE_AUTH=true
ENABLE_RATE_LIMIT=true

# Webhook (optional) — POST JSON alert to this URL on every new capture
# Leave empty to disable. Supports Discord, Slack, custom endpoints, etc.
# WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
WEBHOOK_URL=

```

#### 2. Running the Server

**Development Mode:**
```bash
npm run dev
```

**Production Mode:**
```bash
npm start
```

#### 3. Accessing the Dashboard

Open your browser and navigate to: `http://localhost:3000`

Default credentials:
- **Username:** admin
- **Password:** admin123

> ⚠️ **Important:** Change the default credentials in production!

---

### Python Client Setup

#### 1. Configuration

Edit `config.json` in the `python` directory:

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

#### 2. Running the Client

```bash
python client.py
```

#### 3. Building Standalone Executable

**Windows:**
```bash
pyinstaller --onefile --icon=game.ico --hidden-import=cv2 --hidden-import=geocoder client.py
```

**Linux/macOS:**
```bash
pyinstaller --onefile --hidden-import=cv2 --hidden-import=geocoder client.py
chmod +x dist/client
```

---

### Docker Deployment

#### Using Docker Compose (Recommended)

```bash
cd server

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

#### Using Docker CLI

```bash
# Build image
docker build -t silentcamtrap-server .

# Run container
docker run -d \
  --name silentcamtrap \
  -p 3000:3000 \
  -v $(pwd)/data:/app/data \
  -e SESSION_SECRET=your-secret \
  -e ADMIN_PASSWORD=your-password \
  silentcamtrap-server
```

#### Docker Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NODE_ENV` | Environment mode | production |
| `PORT` | Server port | 3000 |
| `SESSION_SECRET` | Session encryption key | (required) |
| `API_KEY` | Client authentication key | (required) |
| `ADMIN_USERNAME` | Dashboard username | admin |
| `ADMIN_PASSWORD` | Dashboard password | admin123 |
| `ENABLE_AUTH` | Enable authentication | true |
| `ENABLE_RATE_LIMIT` | Enable rate limiting | true |

---

## 🔌 API Reference

### Authentication

All API endpoints (except `/api/health`) require authentication via:
- **Session:** For dashboard access
- **API Key:** For client uploads (header: `X-API-Key`)

### Endpoints

#### Upload Data
```http
POST /api/upload
Content-Type: multipart/form-data
X-API-Key: your-api-key

file: <image file>
data: <JSON data>
```

#### Get All Entries
```http
GET /api/entries?limit=100&offset=0
```

#### Get Single Entry
```http
GET /api/entries/:id
```

#### Delete Entry
```http
DELETE /api/entries/:id
```

#### Get Statistics
```http
GET /api/stats
```

#### Health Check
```http
GET /api/health
```

---

## 📁 Project Structure

```
SilentCamTrap/
├── python/
│   ├── client.py          # Python client script
│   ├── config.json        # Client configuration
│   ├── requirements.txt   # Python dependencies
│   └── game.ico           # Executable icon
├── server/
│   ├── src/
│   │   ├── server.js      # Main server application
│   │   ├── views/         # EJS templates
│   │   │   ├── dashboard.ejs
│   │   │   ├── entries.ejs
│   │   │   ├── entry-detail.ejs
│   │   │   ├── login.ejs
│   │   │   ├── map.ejs
│   │   │   ├── settings.ejs
│   │   │   └── error.ejs
│   │   └── public/        # Static assets
│   ├── data/              # Data storage
│   │   ├── uploads/       # Uploaded images
│   │   └── logs/          # Application logs
│   ├── package.json
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example
├── docs/                  # Documentation
└── README.md
```

---

## 🔐 Security Considerations

1. **Always use HTTPS in production**
2. **Change default credentials immediately**
3. **Use strong API keys**
4. **Configure rate limiting appropriately**
5. **Regular backup of captured data**
6. **Restrict network access to the server**

---

## 🤝 Support

- 📧 **Email:** [Contact Author](https://github.com/mahmud-r-farhan)
- 🐛 **Issues:** [GitHub Issues](https://github.com/mahmud-r-farhan/SilentCamTrap/issues)
- 📚 **Documentation:** [Wiki](https://github.com/mahmud-r-farhan/SilentCamTrap/wiki)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**This software is provided for educational and authorized security testing purposes only.** 

Do not use this software for:
- Unauthorized surveillance
- Privacy invasion
- Any illegal activities

Always obtain proper authorization and comply with local laws before deploying this software.

---

<div align="center">

**Made with ❤️ by [Mahmud Rahman](https://github.com/mahmud-r-farhan)**

</div>