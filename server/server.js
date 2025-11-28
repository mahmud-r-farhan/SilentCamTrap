const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');

const app = express();
const port = 3000;

// Set up storage for uploaded files
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const uploadDir = '../uploads'; 
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir);
    }
    cb(null, uploadDir);
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + path.extname(file.originalname));
  }
});

const upload = multer({ storage: storage });

// Route to handle image and data upload
app.post('/upload', upload.fields([{ name: 'file' }, { name: 'data' }]), (req, res) => {
  if (!req.files['file']) {
    return res.status(400).send('No image uploaded.');
  }
  const imageFilename = req.files['file'][0].filename;
  let extraData = {};
  if (req.files['data']) {
    const dataPath = req.files['data'][0].path;
    extraData = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
    fs.unlinkSync(dataPath);  // Clean up the JSON file after reading
  }
  console.log('Image received:', imageFilename);
  console.log('Extra data:', extraData);
  res.status(200).send('Data uploaded successfully.');
});

app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});