/**
 * SilentCamTrap - Intruder Detection Server
 * ==========================================
 * A comprehensive server for receiving and managing intruder data
 * with a modern EJS-powered dashboard.
 * 
 * @author Mahmud Rahman (https://github.com/mahmud-r-farhan)
 * @license MIT
 */

require('dotenv').config();

const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const compression = require('compression');
const cookieParser = require('cookie-parser');
const session = require('express-session');
const rateLimit = require('express-rate-limit');
const { v4: uuidv4 } = require('uuid');
const bcrypt = require('bcryptjs');

// =============================================================================
// Configuration
// =============================================================================

const config = {
    port: process.env.PORT || 3000,
    nodeEnv: process.env.NODE_ENV || 'development',
    sessionSecret: process.env.SESSION_SECRET || 'change-me-in-production',
    apiKey: process.env.API_KEY || 'default-api-key',
    adminUsername: process.env.ADMIN_USERNAME || 'admin',
    adminPassword: process.env.ADMIN_PASSWORD || 'admin123',
    rateLimitWindowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS) || 15 * 60 * 1000,
    rateLimitMax: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS) || 100,
    maxFileSizeMB: parseInt(process.env.MAX_FILE_SIZE_MB) || 10,
    uploadDir: process.env.UPLOAD_DIR || path.join(__dirname, '../data/uploads'),
    logsDir: process.env.LOGS_DIR || path.join(__dirname, '../data/logs'),
    enableAuth: process.env.ENABLE_AUTH !== 'false',
    enableRateLimit: process.env.ENABLE_RATE_LIMIT !== 'false',
    webhookUrl: process.env.WEBHOOK_URL || null   // optional: POST alert on new capture
};

// =============================================================================
// Express App Setup
// =============================================================================

const app = express();

// Create required directories
[config.uploadDir, config.logsDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// =============================================================================
// Middleware
// =============================================================================

// Security headers (modified for EJS)
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com', 'https://unpkg.com'],
            fontSrc: ["'self'", 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
            scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", 'https://cdnjs.cloudflare.com', 'https://unpkg.com'],
            imgSrc: ["'self'", 'data:', 'blob:', '*', 'https://*.basemaps.cartocdn.com', 'https://*.tile.openstreetmap.org', 'https://server.arcgisonline.com', 'https://*.tile.opentopomap.org'],
            connectSrc: ["'self'"]
        }
    }
}));

// Compression
app.use(compression());

// CORS
app.use(cors({
    origin: config.nodeEnv === 'production' ? false : '*',
    credentials: true
}));

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cookieParser());

// Session
app.use(session({
    secret: config.sessionSecret,
    resave: false,
    saveUninitialized: false,
    cookie: {
        secure: config.nodeEnv === 'production',
        httpOnly: true,
        maxAge: 24 * 60 * 60 * 1000 // 24 hours
    }
}));

// Logging
if (!fs.existsSync(config.logsDir)) {
    fs.mkdirSync(config.logsDir, { recursive: true });
}
const accessLogStream = fs.createWriteStream(
    path.join(config.logsDir, 'access.log'),
    { flags: 'a' }
);
app.use(morgan('combined', { stream: accessLogStream }));
app.use(morgan('dev'));

// Rate limiting
if (config.enableRateLimit) {
    const limiter = rateLimit({
        windowMs: config.rateLimitWindowMs,
        max: config.rateLimitMax,
        message: { error: 'Too many requests, please try again later.' }
    });
    app.use('/api/', limiter);
}

// Static files
app.use('/uploads', express.static(config.uploadDir, { maxAge: '1h', etag: true }));
app.use('/static', express.static(path.join(__dirname, 'public'), { maxAge: '1d', etag: true }));

// View engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// =============================================================================
// File Upload Configuration
// =============================================================================

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        const dateFolder = new Date().toISOString().split('T')[0];
        const uploadPath = path.join(config.uploadDir, dateFolder);

        if (!fs.existsSync(uploadPath)) {
            fs.mkdirSync(uploadPath, { recursive: true });
        }

        cb(null, uploadPath);
    },
    filename: (req, file, cb) => {
        const uniqueId = uuidv4();
        const ext = path.extname(file.originalname);
        cb(null, `${uniqueId}${ext}`);
    }
});

const fileFilter = (req, file, cb) => {
    if (file.fieldname === 'file') {
        // Allow images
        if (file.mimetype.startsWith('image/')) {
            cb(null, true);
        } else {
            cb(new Error('Only image files are allowed'), false);
        }
    } else if (file.fieldname === 'data') {
        // Allow JSON
        if (file.mimetype === 'application/json') {
            cb(null, true);
        } else {
            cb(new Error('Only JSON data is allowed'), false);
        }
    } else {
        cb(null, true);
    }
};

const upload = multer({
    storage,
    fileFilter,
    limits: {
        fileSize: config.maxFileSizeMB * 1024 * 1024
    }
});

// =============================================================================
// Data Store (In-memory with file persistence)
// =============================================================================

class IntruderDataStore {
    constructor(dataFile) {
        this.dataFile = dataFile;
        this.data = [];
        this.load();
    }

    load() {
        try {
            if (fs.existsSync(this.dataFile)) {
                const content = fs.readFileSync(this.dataFile, 'utf8');
                this.data = JSON.parse(content);
            }
        } catch (error) {
            console.error('Error loading data:', error);
            this.data = [];
        }
    }

    save() {
        try {
            const dir = path.dirname(this.dataFile);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            fs.writeFileSync(this.dataFile, JSON.stringify(this.data, null, 2));
        } catch (error) {
            console.error('Error saving data:', error);
        }
    }

    add(entry) {
        const newEntry = {
            id: uuidv4(),
            timestamp: new Date().toISOString(),
            ...entry
        };
        this.data.unshift(newEntry);
        this.save();
        return newEntry;
    }

    getAll(limit = 100, offset = 0) {
        return this.data.slice(offset, offset + limit);
    }

    getById(id) {
        return this.data.find(entry => entry.id === id);
    }

    delete(id) {
        const index = this.data.findIndex(entry => entry.id === id);
        if (index > -1) {
            const entry = this.data[index];
            this.data.splice(index, 1);
            this.save();
            return entry;
        }
        return null;
    }

    count() {
        return this.data.length;
    }

    getStats() {
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

        return {
            total: this.data.length,
            today: this.data.filter(e => new Date(e.timestamp) >= today).length,
            thisWeek: this.data.filter(e => new Date(e.timestamp) >= weekAgo).length,
            countries: [...new Set(this.data.map(e => e.extraData?.location?.country).filter(Boolean))],
            recentLocations: this.data.slice(0, 10).map(e => ({
                lat: e.extraData?.location?.latitude,
                lng: e.extraData?.location?.longitude,
                city: e.extraData?.location?.city
            })).filter(l => l.lat && l.lng)
        };
    }
}

const dataStore = new IntruderDataStore(path.join(config.logsDir, 'intruder_data.json'));

// =============================================================================
// Authentication Middleware
// =============================================================================

const requireAuth = (req, res, next) => {
    if (!config.enableAuth) {
        return next();
    }

    if (req.session && req.session.authenticated) {
        return next();
    }

    if (req.xhr || req.headers.accept?.includes('application/json')) {
        return res.status(401).json({ error: 'Authentication required' });
    }

    res.redirect('/login');
};

const requireApiKey = (req, res, next) => {
    // Accept X-API-KEY, x-api-key, or ?apiKey= query param
    const apiKey =
        req.headers['x-api-key'] ||
        req.headers['X-API-KEY'] ||
        req.query.apiKey;

    if (!config.enableAuth || apiKey === config.apiKey) {
        return next();
    }

    res.status(401).json({ error: 'Invalid API key' });
};

// =============================================================================
// Webhook Notification
// =============================================================================

/**
 * Send a webhook POST when a new intruder capture arrives.
 * @param {object} entry - The new dataStore entry
 */
async function sendWebhook(entry) {
    if (!config.webhookUrl) return;
    try {
        const https = require('https');
        const http = require('http');
        const url = new URL(config.webhookUrl);
        const body = JSON.stringify({
            event: 'new_capture',
            id: entry.id,
            timestamp: entry.timestamp,
            ip: entry.extraData?.network?.public_ip || entry.clientIp || 'Unknown',
            location: {
                city: entry.extraData?.location?.city || null,
                country: entry.extraData?.location?.country || null,
                lat: entry.extraData?.location?.latitude || null,
                lng: entry.extraData?.location?.longitude || null,
            },
            system: {
                username: entry.extraData?.system?.username || null,
                os: `${entry.extraData?.system?.os_name || ''} ${entry.extraData?.system?.os_release || ''}`.trim(),
            },
        });

        const options = {
            hostname: url.hostname,
            port: url.port || (url.protocol === 'https:' ? 443 : 80),
            path: url.pathname + url.search,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(body),
                'User-Agent': 'SilentCamTrap/1.0',
            },
        };

        const transport = url.protocol === 'https:' ? https : http;
        const req = transport.request(options);
        req.on('error', () => {}); // ignore webhook errors silently
        req.write(body);
        req.end();
        console.log(`[Webhook] Notification sent to ${config.webhookUrl}`);
    } catch (err) {
        console.warn('[Webhook] Failed to send notification:', err.message);
    }
}

// =============================================================================
// Helper: Render with Layout
// =============================================================================

const renderPage = (res, view, data = {}) => {
    res.render(view, data);
};

// =============================================================================
// Routes: Authentication
// =============================================================================

app.get('/login', (req, res) => {
    if (req.session?.authenticated) {
        return res.redirect('/');
    }
    res.render('login', { error: null });
});

app.post('/login', async (req, res) => {
    const { username, password } = req.body;

    if (username === config.adminUsername && password === config.adminPassword) {
        req.session.authenticated = true;
        req.session.username = username;
        return res.redirect('/');
    }

    res.render('login', { error: 'Invalid credentials' });
});

app.get('/logout', (req, res) => {
    req.session.destroy();
    res.redirect('/login');
});

// =============================================================================
// Educational Simulation Store & Logic
// All components are non-functional educational demonstrations with dummy data.
// =============================================================================

class SimulationStore {
    constructor() {
        this.selectedTarget = 'simulated-user-01';
        this.intervalSeconds = 30;
        this.backgroundModeEnabled = true;
        this.simulationLogs = [
            { id: uuidv4(), timestamp: new Date(Date.now() - 300000).toISOString(), target: 'simulated-user-01', action: 'Heartbeat Check', status: 'Active (Sandboxed)', info: 'Educational Simulation Active' },
            { id: uuidv4(), timestamp: new Date(Date.now() - 120000).toISOString(), target: 'simulated-user-01', action: 'Backdoor Handshake', status: 'Completed', info: 'Simulated backdoor ping received' }
        ];
        this.pendingCommands = [];
        this.targets = [
            { id: 'simulated-user-01', username: 'workstation-corp-01\\jdoe', ip: '192.168.1.105', os: 'Windows 11 Enterprise (Simulated)', status: 'Online', lastSeen: new Date().toISOString() },
            { id: 'simulated-user-02', username: 'lab-pc-02\\analyst', ip: '192.168.1.112', os: 'Ubuntu 22.04 LTS (Simulated)', status: 'Online', lastSeen: new Date().toISOString() },
            { id: 'simulated-user-03', username: 'executive-laptop\\ceo', ip: '10.0.0.45', os: 'macOS Sonoma (Simulated)', status: 'Idle', lastSeen: new Date(Date.now() - 600000).toISOString() }
        ];
        this.mockFiles = [
            { id: 'file-1', name: 'Q4_Financial_Report_CONFIDENTIAL.pdf', size: '2.4 MB', path: '/Documents/Financials/', category: 'Document', riskLevel: 'High (Dummy Data)' },
            { id: 'file-2', name: 'passwords_backup_mock.kdbx', size: '512 KB', path: '/Users/jdoe/Desktop/', category: 'Vault', riskLevel: 'Critical (Dummy Data)' },
            { id: 'file-3', name: 'customer_emails_sample.csv', size: '12.8 MB', path: '/Downloads/', category: 'Database', riskLevel: 'Medium (Dummy Data)' },
            { id: 'file-4', name: 'system_architecture_diagram.png', size: '4.1 MB', path: '/Pictures/', category: 'Image', riskLevel: 'Low (Dummy Data)' },
            { id: 'file-5', name: 'network_keys_test.pem', size: '1.2 KB', path: '/.ssh/', category: 'Key', riskLevel: 'Critical (Dummy Data)' }
        ];
        this.dataTransfers = [
            { id: 'transfer-1', filename: 'passwords_backup_mock.kdbx', size: '512 KB', speed: '1.2 MB/s', progress: 100, status: 'Completed (Simulated)', timestamp: new Date(Date.now() - 180000).toISOString() },
            { id: 'transfer-2', filename: 'customer_emails_sample.csv', size: '12.8 MB', speed: '3.4 MB/s', progress: 100, status: 'Completed (Simulated)', timestamp: new Date(Date.now() - 60000).toISOString() }
        ];
        this.remoteSessions = [
            { id: 'rem-101', anydeskId: '984 210 339', status: 'Simulated Session Active', quality: 'HD 60fps (Mock)', encrypted: 'TLS 1.3 (Simulated)' }
        ];
        this.mockWebcamCaptures = [
            {
                id: 'webcam-1',
                timestamp: new Date().toISOString(),
                label: 'Simulated Peripheral Capture (Dummy Image)',
                svgDataUri: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="100%" height="100%" fill="%230f172a"/><circle cx="320" cy="200" r="80" fill="%23334155"/><circle cx="320" cy="170" r="35" fill="%2364748b"/><path d="M 220 310 Q 320 250 420 310 Z" fill="%2364748b"/><text x="320" y="380" font-family="sans-serif" font-size="20" fill="%2338bdf8" text-anchor="middle">[ EDUCATIONAL WEBCAM SIMULATION ]</text><text x="320" y="410" font-family="sans-serif" font-size="14" fill="%2394a3b8" text-anchor="middle">Dummy Peripheral Feed - Under Development</text></svg>'
            }
        ];
    }

    addLog(target, action, status, info) {
        this.simulationLogs.unshift({
            id: uuidv4(),
            timestamp: new Date().toISOString(),
            target: target || this.selectedTarget,
            action,
            status,
            info
        });
        if (this.simulationLogs.length > 100) this.simulationLogs.pop();
    }

    addCommand(target, action, params = {}) {
        const cmd = {
            id: uuidv4(),
            target,
            action,
            params,
            timestamp: new Date().toISOString(),
            status: 'pending'
        };
        this.pendingCommands.push(cmd);
        this.addLog(target, `Command Triggered: ${action}`, 'Pending', `Parameters: ${JSON.stringify(params)}`);
        return cmd;
    }

    getPendingCommandsForTarget(target) {
        const cmds = this.pendingCommands.filter(c => (c.target === 'all' || c.target === target) && c.status === 'pending');
        cmds.forEach(c => { c.status = 'dispatched'; });
        return cmds;
    }
}

const simulationStore = new SimulationStore();

// =============================================================================
// Routes: Dashboard (EJS)
// =============================================================================

app.get('/', requireAuth, (req, res) => {
    const stats = dataStore.getStats();
    const recentEntries = dataStore.getAll(10);

    res.render('dashboard', {
        title: 'Dashboard',
        stats,
        recentEntries,
        username: req.session?.username || 'Admin'
    });
});

app.get('/entries', requireAuth, (req, res) => {
    const page = parseInt(req.query.page) || 1;
    const limit = 20;
    const offset = (page - 1) * limit;

    const entries = dataStore.getAll(limit, offset);
    const total = dataStore.count();
    const totalPages = Math.ceil(total / limit);

    res.render('entries', {
        title: 'All Entries',
        entries,
        page,
        totalPages,
        total,
        username: req.session?.username || 'Admin'
    });
});

app.get('/entry/:id', requireAuth, (req, res) => {
    const entry = dataStore.getById(req.params.id);

    if (!entry) {
        return res.status(404).render('error', {
            title: 'Not Found',
            message: 'Entry not found',
            username: req.session?.username || 'Admin'
        });
    }

    res.render('entry-detail', {
        title: 'Entry Details',
        entry,
        username: req.session?.username || 'Admin'
    });
});

app.get('/map', requireAuth, (req, res) => {
    const entries = dataStore.getAll(100);
    const locations = entries
        .filter(e => e.extraData?.location?.latitude && e.extraData?.location?.longitude)
        .map(e => ({
            id: e.id,
            lat: e.extraData.location.latitude,
            lng: e.extraData.location.longitude,
            city: e.extraData.location.city,
            country: e.extraData.location.country,
            timestamp: e.timestamp,
            image: e.imagePath
        }));

    res.render('map', {
        title: 'Location Map',
        locations: JSON.stringify(locations),
        username: req.session?.username || 'Admin'
    });
});

app.get('/settings', requireAuth, (req, res) => {
    res.render('settings', {
        title: 'Settings',
        config: {
            enableAuth: config.enableAuth,
            enableRateLimit: config.enableRateLimit,
            maxFileSizeMB: config.maxFileSizeMB
        },
        username: req.session?.username || 'Admin'
    });
});

app.get('/simulations', requireAuth, (req, res) => {
    res.render('simulations', {
        title: 'Educational Simulations',
        simulation: simulationStore,
        username: req.session?.username || 'Admin'
    });
});

// =============================================================================
// Educational Simulation API Endpoints
// Strict educational simulation endpoints using sandbox/dummy data only.
// =============================================================================

// Target Selection & Simulation Configuration
app.post('/api/simulation/target', requireAuth, (req, res) => {
    const { targetId } = req.body;
    if (targetId) {
        simulationStore.selectedTarget = targetId;
        simulationStore.addLog(targetId, 'Target Selected', 'Active', 'Simulated target changed');
    }
    res.json({ success: true, selectedTarget: simulationStore.selectedTarget });
});

app.post('/api/simulation/config', requireAuth, (req, res) => {
    const { intervalSeconds, backgroundModeEnabled } = req.body;
    if (intervalSeconds !== undefined) {
        simulationStore.intervalSeconds = parseInt(intervalSeconds, 10) || 30;
    }
    if (backgroundModeEnabled !== undefined) {
        simulationStore.backgroundModeEnabled = Boolean(backgroundModeEnabled);
    }
    simulationStore.addLog(simulationStore.selectedTarget, 'Simulation Settings Updated', 'Configured', `Interval: ${simulationStore.intervalSeconds}s, Background: ${simulationStore.backgroundModeEnabled}`);
    res.json({
        success: true,
        intervalSeconds: simulationStore.intervalSeconds,
        backgroundModeEnabled: simulationStore.backgroundModeEnabled
    });
});

// Trigger Screen Overlay Demonstration ("Removing virus" / "Please wait.")
app.post('/api/simulation/trigger-screen', requireAuth, (req, res) => {
    const { targetId, durationSeconds } = req.body;
    const target = targetId || simulationStore.selectedTarget;
    const cmd = simulationStore.addCommand(target, 'TRIGGER_SCREEN_OVERLAY', {
        title: 'Removing virus',
        subtitle: 'Please wait.',
        durationSeconds: durationSeconds || 5
    });
    res.json({
        success: true,
        message: 'Educational screen overlay demonstration triggered',
        command: cmd
    });
});

// Trigger Mock File Transfer
app.post('/api/simulation/trigger-transfer', requireAuth, (req, res) => {
    const { fileId, targetId } = req.body;
    const target = targetId || simulationStore.selectedTarget;
    const mockFile = simulationStore.mockFiles.find(f => f.id === fileId) || simulationStore.mockFiles[0];

    const transfer = {
        id: uuidv4(),
        filename: mockFile.name,
        size: mockFile.size,
        speed: '2.5 MB/s',
        progress: 100,
        status: 'Completed (Simulated Data)',
        timestamp: new Date().toISOString()
    };
    simulationStore.dataTransfers.unshift(transfer);
    simulationStore.addLog(target, 'Data Transfer Simulated', 'Completed', `Exfiltrated dummy file: ${mockFile.name}`);

    res.json({ success: true, transfer });
});

// Trigger Mock Webcam Capture Demonstration
app.post('/api/simulation/trigger-webcam', requireAuth, (req, res) => {
    const { targetId } = req.body;
    const target = targetId || simulationStore.selectedTarget;

    const capture = {
        id: uuidv4(),
        timestamp: new Date().toISOString(),
        label: `Simulated Peripheral Capture (${target})`,
        svgDataUri: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="100%" height="100%" fill="%230f172a"/><circle cx="320" cy="200" r="80" fill="%230284c7"/><circle cx="320" cy="170" r="35" fill="%2338bdf8"/><path d="M 220 310 Q 320 250 420 310 Z" fill="%2338bdf8"/><text x="320" y="370" font-family="sans-serif" font-size="20" fill="%23f87171" text-anchor="middle">[ SIMULATED WEBCAM DEMONSTRATION ]</text><text x="320" y="400" font-family="sans-serif" font-size="14" fill="%23e2e8f0" text-anchor="middle">Target: ${target} - Educational Sandboxed Image</text></svg>`
    };

    simulationStore.mockWebcamCaptures.unshift(capture);
    simulationStore.addLog(target, 'Webcam Module Simulated', 'Captured', 'Dummy peripheral image generated');

    res.json({ success: true, capture });
});

// Client Heartbeat & Command Polling
app.get('/api/simulation/poll', (req, res) => {
    const targetId = req.query.targetId || 'simulated-user-01';
    const pendingCommands = simulationStore.getPendingCommandsForTarget(targetId);

    res.json({
        success: true,
        intervalSeconds: simulationStore.intervalSeconds,
        backgroundModeEnabled: simulationStore.backgroundModeEnabled,
        pendingCommands
    });
});

// Client Simulation Status Heartbeat Report
app.post('/api/simulation/heartbeat', (req, res) => {
    const { targetId, status, info } = req.body;
    simulationStore.addLog(
        targetId || 'simulated-user-01',
        'Background Heartbeat',
        status || 'Active (Sandboxed)',
        info || 'Client active in simulation background mode'
    );
    res.json({ success: true });
});

// Reset Simulation Logs
app.post('/api/simulation/reset', requireAuth, (req, res) => {
    simulationStore.simulationLogs = [];
    simulationStore.addLog(simulationStore.selectedTarget, 'Simulation Reset', 'Initialized', 'Simulation state reset for educational lab');
    res.json({ success: true, message: 'Simulation logs reset' });
});

// =============================================================================
// Routes: API
// =============================================================================

// Upload endpoint for Python client
app.post('/api/upload', requireApiKey, upload.fields([
    { name: 'file', maxCount: 1 },
    { name: 'data', maxCount: 1 }
]), (req, res) => {
    try {
        if (!req.files?.file) {
            return res.status(400).json({ error: 'No image uploaded' });
        }

        const imageFile = req.files.file[0];
        const dateFolder = new Date().toISOString().split('T')[0];
        const relativePath = `${dateFolder}/${imageFile.filename}`;

        let extraData = {};
        if (req.files?.data) {
            const dataPath = req.files.data[0].path;
            try {
                extraData = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
                fs.unlinkSync(dataPath);
            } catch (error) {
                console.error('Error parsing JSON data:', error);
            }
        }

        const entry = dataStore.add({
            imagePath: relativePath,
            imageFilename: imageFile.filename,
            extraData,
            clientIp: req.ip || req.connection?.remoteAddress
        });

        console.log(`[${new Date().toISOString()}] New intruder captured:`, {
            id: entry.id,
            ip: extraData.network?.public_ip || 'Unknown',
            location: extraData.location?.city || 'Unknown',
            user: extraData.system?.username || 'Unknown',
        });

        // Fire webhook notification (non-blocking)
        sendWebhook(entry).catch(() => {});

        res.status(200).json({
            success: true,
            message: 'Data uploaded successfully',
            id: entry.id
        });

    } catch (error) {
        console.error('Upload error:', error);
        res.status(500).json({ error: 'Upload failed' });
    }
});

// Legacy upload endpoint (for compatibility)
app.post('/upload', requireApiKey, upload.fields([
    { name: 'file', maxCount: 1 },
    { name: 'data', maxCount: 1 }
]), (req, res) => {
    // Same as /api/upload
    try {
        if (!req.files?.file) {
            return res.status(400).json({ error: 'No image uploaded' });
        }

        const imageFile = req.files.file[0];
        const dateFolder = new Date().toISOString().split('T')[0];
        const relativePath = `${dateFolder}/${imageFile.filename}`;

        let extraData = {};
        if (req.files?.data) {
            const dataPath = req.files.data[0].path;
            try {
                extraData = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
                fs.unlinkSync(dataPath);
            } catch (error) {
                console.error('Error parsing JSON data:', error);
            }
        }

        const entry = dataStore.add({
            imagePath: relativePath,
            imageFilename: imageFile.filename,
            extraData,
            clientIp: req.ip || req.connection?.remoteAddress
        });

        console.log(`[${new Date().toISOString()}] New intruder captured (legacy):`, {
            id: entry.id,
            ip: extraData.network?.public_ip || 'Unknown',
            location: extraData.location?.city || 'Unknown'
        });

        res.status(200).send('Data uploaded successfully.');

    } catch (error) {
        console.error('Upload error:', error);
        res.status(500).send('Upload failed');
    }
});

// Get all entries
app.get('/api/entries', requireAuth, (req, res) => {
    const limit = parseInt(req.query.limit) || 100;
    const offset = parseInt(req.query.offset) || 0;

    const entries = dataStore.getAll(limit, offset);
    const total = dataStore.count();

    res.json({
        success: true,
        data: entries,
        total,
        limit,
        offset
    });
});

// Get single entry
app.get('/api/entries/:id', requireAuth, (req, res) => {
    const entry = dataStore.getById(req.params.id);

    if (!entry) {
        return res.status(404).json({ error: 'Entry not found' });
    }

    res.json({ success: true, data: entry });
});

// Delete entry
app.delete('/api/entries/:id', requireAuth, (req, res) => {
    const entry = dataStore.delete(req.params.id);

    if (!entry) {
        return res.status(404).json({ error: 'Entry not found' });
    }

    // Delete associated image
    const imagePath = path.join(config.uploadDir, entry.imagePath);
    if (fs.existsSync(imagePath)) {
        fs.unlinkSync(imagePath);
    }

    res.json({ success: true, message: 'Entry deleted' });
});

// Get statistics
app.get('/api/stats', requireAuth, (req, res) => {
    res.json({
        success: true,
        data: dataStore.getStats()
    });
});

// Export all entries as CSV
app.get('/api/export/csv', requireAuth, (req, res) => {
    const entries = dataStore.getAll(10000);

    const headers = [
        'id', 'timestamp', 'client_ip',
        'public_ip', 'local_ip', 'hostname', 'mac_address', 'wifi_ssid',
        'latitude', 'longitude', 'city', 'state', 'country', 'isp', 'timezone',
        'os_name', 'os_release', 'machine', 'processor',
        'username', 'screen_width', 'screen_height',
        'ram_total_gb', 'disk_free_gb', 'battery_percent', 'uptime_seconds',
        'image_path'
    ];

    const escape = (v) => {
        if (v === null || v === undefined) return '';
        const s = String(v);
        return s.includes(',') || s.includes('"') || s.includes('\n')
            ? `"${s.replace(/"/g, '""')}"`
            : s;
    };

    const rows = entries.map(e => [
        e.id,
        e.timestamp,
        e.clientIp || '',
        e.extraData?.network?.public_ip || '',
        e.extraData?.network?.local_ip || '',
        e.extraData?.network?.hostname || '',
        e.extraData?.network?.mac_address || '',
        e.extraData?.network?.wifi_ssid || '',
        e.extraData?.location?.latitude || '',
        e.extraData?.location?.longitude || '',
        e.extraData?.location?.city || '',
        e.extraData?.location?.state || '',
        e.extraData?.location?.country || '',
        e.extraData?.location?.isp || '',
        e.extraData?.location?.timezone || '',
        e.extraData?.system?.os_name || '',
        e.extraData?.system?.os_release || '',
        e.extraData?.system?.machine || '',
        e.extraData?.system?.processor || '',
        e.extraData?.system?.username || '',
        e.extraData?.system?.screen_width || '',
        e.extraData?.system?.screen_height || '',
        e.extraData?.system?.ram_total_gb || '',
        e.extraData?.system?.disk_free_gb || '',
        e.extraData?.system?.battery_percent || '',
        e.extraData?.system?.uptime_seconds || '',
        e.imagePath || '',
    ].map(escape).join(','));

    const csv = [headers.join(','), ...rows].join('\r\n');
    const filename = `silentcamtrap_export_${new Date().toISOString().split('T')[0]}.csv`;

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send('\uFEFF' + csv); // BOM for Excel compatibility
});

// Export all entries as JSON
app.get('/api/export/json', requireAuth, (req, res) => {
    const entries = dataStore.getAll(10000);
    const filename = `silentcamtrap_export_${new Date().toISOString().split('T')[0]}.json`;
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.json({ exported_at: new Date().toISOString(), count: entries.length, data: entries });
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({
        status: 'healthy',
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

// =============================================================================
// Error Handling
// =============================================================================

app.use((req, res) => {
    if (req.xhr || req.headers.accept?.includes('application/json')) {
        return res.status(404).json({ error: 'Not found' });
    }
    res.status(404).render('error', {
        title: 'Not Found',
        message: 'Page not found',
        username: req.session?.username || 'Guest'
    });
});

app.use((err, req, res, next) => {
    console.error('Error:', err);

    if (err instanceof multer.MulterError) {
        return res.status(400).json({ error: `Upload error: ${err.message}` });
    }

    if (req.xhr || req.headers.accept?.includes('application/json')) {
        return res.status(500).json({ error: 'Internal server error' });
    }

    res.status(500).render('error', {
        title: 'Error',
        message: config.nodeEnv === 'development' ? err.message : 'Something went wrong',
        username: req.session?.username || 'Guest'
    });
});

// =============================================================================
// Start Server
// =============================================================================

app.listen(config.port, () => {
    console.log(`
╔══════════════════════════════════════════════════════════════╗
║                 🔒  SilentCamTrap Server                      ║
╠══════════════════════════════════════════════════════════════╣
║  Dashboard : http://localhost:${config.port.toString().padEnd(29)}║
║  Environment: ${config.nodeEnv.padEnd(44)}║
║  Auth enabled: ${config.enableAuth.toString().padEnd(43)}║
║  Webhook  : ${(config.webhookUrl || 'disabled').slice(0, 46).padEnd(47)}║
║  Login    : admin / admin123  (change in .env!)              ║
║  Export   : GET /api/export/csv  or  /api/export/json        ║
╚══════════════════════════════════════════════════════════════╝
    `);
});

module.exports = app;
