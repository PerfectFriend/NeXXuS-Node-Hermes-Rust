# HOT
const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;

// Resolve paths relative to workspace root (parent of server_node)
const WORKSPACE_ROOT = path.resolve(__dirname, '..');

const APK_PATHS = [
  path.join(WORKSPACE_ROOT, 'apk', 'app-debug.apk'),
  path.join(WORKSPACE_ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')
];

const ZIP_PATHS = [
  path.join(WORKSPACE_ROOT, 'apk', 'app-debug-full.zip'),
  path.join(WORKSPACE_ROOT, 'apk', 'app-debug.zip')
];

function findExistingFile(paths) {
  for (const p of paths) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return null;
}

// Request Logger
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Root Route - Elegant HTML Landing Page with Download Buttons
app.get('/', (req, res) => {
  const apkPath = findExistingFile(APK_PATHS);
  const zipPath = findExistingFile(ZIP_PATHS);

  const apkExists = !!apkPath;
  const zipExists = !!zipPath;

  const apkSize = apkExists ? (fs.statSync(apkPath).size / (1024 * 1024)).toFixed(2) + ' MB' : 'Not available';
  const zipSize = zipExists ? (fs.statSync(zipPath).size / (1024 * 1024)).toFixed(2) + ' MB' : 'Not available';

  const html = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Download Center - Android APK</title>
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        :root {
          --bg-color: #0f172a;
          --card-bg: #1e293b;
          --primary: #3b82f6;
          --primary-hover: #2563eb;
          --success: #10b981;
          --success-hover: #059669;
          --text-main: #f8fafc;
          --text-muted: #94a3b8;
          --border: #334155;
        }
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        body {
          font-family: 'Plus Jakarta Sans', sans-serif;
          background-color: var(--bg-color);
          color: var(--text-main);
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          padding: 24px;
        }
        .container {
          background-color: var(--card-bg);
          border: 1px solid var(--border);
          border-radius: 24px;
          padding: 40px;
          max-width: 600px;
          width: 100%;
          box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.3);
          text-align: center;
        }
        h1 {
          font-size: 2rem;
          font-weight: 700;
          margin-bottom: 12px;
          background: linear-gradient(135deg, #60a5fa, #3b82f6);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .subtitle {
          font-size: 1rem;
          color: var(--text-muted);
          margin-bottom: 32px;
        }
        .file-card {
          background: rgba(15, 23, 42, 0.4);
          border: 1px solid var(--border);
          border-radius: 16px;
          padding: 24px;
          margin-bottom: 20px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
        }
        .file-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .file-title {
          font-size: 1.1rem;
          font-weight: 600;
        }
        .file-meta {
          font-size: 0.85rem;
          color: var(--text-muted);
        }
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 14px 28px;
          font-size: 1rem;
          font-weight: 600;
          text-decoration: none;
          color: #ffffff;
          border-radius: 12px;
          transition: all 0.2s ease-in-out;
          width: 100%;
          cursor: pointer;
        }
        .btn-apk {
          background-color: var(--primary);
        }
        .btn-apk:hover {
          background-color: var(--primary-hover);
          transform: translateY(-2px);
        }
        .btn-zip {
          background-color: var(--success);
        }
        .btn-zip:hover {
          background-color: var(--success-hover);
          transform: translateY(-2px);
        }
        .btn-disabled {
          background-color: #475569;
          color: #94a3b8;
          cursor: not-allowed;
          pointer-events: none;
        }
        .badge {
          font-size: 0.75rem;
          padding: 4px 8px;
          border-radius: 6px;
          font-weight: 600;
          text-transform: uppercase;
        }
        .badge-available {
          background-color: rgba(16, 185, 129, 0.2);
          color: #34d399;
        }
        .badge-missing {
          background-color: rgba(239, 68, 68, 0.2);
          color: #f87171;
        }
        .instructions {
          margin-top: 32px;
          padding-top: 24px;
          border-top: 1px solid var(--border);
          text-align: left;
        }
        .instructions h3 {
          font-size: 1rem;
          margin-bottom: 8px;
          color: var(--text-main);
        }
        .instructions ol {
          margin-left: 20px;
          font-size: 0.9rem;
          color: var(--text-muted);
          line-height: 1.6;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>Download Center</h1>
        <p class="subtitle">Directly download Android APK or ZIP files from your Google AI Studio container.</p>

        <!-- APK Card -->
        <div class="file-card">
          <div class="file-info">
            <span class="file-title">Android Application package (APK)</span>
            <span class="file-meta">Size: ${apkSize} &bull; <span class="badge ${apkExists ? 'badge-available' : 'badge-missing'}">${apkExists ? 'Ready' : 'Not Found'}</span></span>
          </div>
          <a href="/download/release.apk" class="btn btn-apk ${apkExists ? '' : 'btn-disabled'}">Download APK File</a>
        </div>

        <!-- ZIP Card -->
        <div class="file-card">
          <div class="file-info">
            <span class="file-title">ZIP Compressed Archive (Full)</span>
            <span class="file-meta">Size: ${zipSize} &bull; <span class="badge ${zipExists ? 'badge-available' : 'badge-missing'}">${zipExists ? 'Ready' : 'Not Found'}</span></span>
          </div>
          <a href="/download/release.zip" class="btn btn-zip ${zipExists ? '' : 'btn-disabled'}">Download ZIP Archive</a>
        </div>

        <div class="instructions">
          <h3>How to install APK:</h3>
          <ol>
            <li>Download the APK file above directly to your computer or Android device.</li>
            <li>If downloaded to PC, transfer it to your Android device via USB, cloud, or email.</li>
            <li>On your Android device, open any File Manager, tap the downloaded APK file.</li>
            <li>Allow installation from "Unknown sources" if prompted, then complete the setup.</li>
          </ol>
        </div>
      </div>
    </body>
    </html>
  `;
  res.send(html);
});

// Route for streaming APK
app.get('/download/release.apk', (req, res) => {
  const apkPath = findExistingFile(APK_PATHS);
  
  if (!apkPath) {
    return res.status(404).send('APK file not found. Make sure you ran the compile step.');
  }

  const stat = fs.statSync(apkPath);
  
  // Set headers exactly as outlined in the user instructions
  res.setHeader('Content-Type', 'application/vnd.android.package-archive');
  res.setHeader('Content-Length', stat.size);
  res.setHeader('Content-Disposition', 'attachment; filename="app-debug.apk"');

  console.log(`Streaming APK of size: ${(stat.size / (1024 * 1024)).toFixed(2)} MB`);
  const stream = fs.createReadStream(apkPath);
  stream.pipe(res);
});

// Route for streaming ZIP
app.get('/download/release.zip', (req, res) => {
  const zipPath = findExistingFile(ZIP_PATHS);

  if (!zipPath) {
    return res.status(404).send('ZIP file not found. Make sure you generated the zip archive.');
  }

  const stat = fs.statSync(zipPath);

  // Set headers exactly as outlined in the user instructions
  res.setHeader('Content-Type', 'application/zip');
  res.setHeader('Content-Length', stat.size);
  res.setHeader('Content-Disposition', 'attachment; filename="app-debug-full.zip"');

  console.log(`Streaming ZIP of size: ${(stat.size / (1024 * 1024)).toFixed(2)} MB`);
  const stream = fs.createReadStream(zipPath);
  stream.pipe(res);
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Download server running at http://localhost:${PORT}`);
  console.log(`Ready to serve APK and ZIP files.`);
});
