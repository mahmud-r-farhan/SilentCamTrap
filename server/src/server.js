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
    enableRateLimit: process.env.ENABLE_RATE_LIMIT !== 'false'
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
            imgSrc: ["'self'", 'data:', 'blob:', '*', 'https://*.basemaps.cartocdn.com', 'https://*.tile.openstreetmap.org'],
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
app.use('/uploads', express.static(config.uploadDir));
app.use('/static', express.static(path.join(__dirname, 'public')));

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
    const apiKey = req.headers['x-api-key'] || req.query.apiKey;

    if (!config.enableAuth || apiKey === config.apiKey) {
        return next();
    }

    res.status(401).json({ error: 'Invalid API key' });
};

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
            location: extraData.location?.city || 'Unknown'
        });

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
║                    🔒 SilentCamTrap Server                    ║
╠══════════════════════════════════════════════════════════════╣
║  Server running on: http://localhost:${config.port.toString().padEnd(26)}║
║  Environment: ${config.nodeEnv.padEnd(44)}║
║  Auth enabled: ${config.enableAuth.toString().padEnd(43)}║
║  Default login: admin / admin123                             ║
╚══════════════════════════════════════════════════════════════╝
    `);
});

module.exports = app;
