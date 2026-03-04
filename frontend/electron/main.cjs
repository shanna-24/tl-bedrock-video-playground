const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8001;  // Use different port from browser dev (8000)

// Determine if running in development or production
const isDev = !app.isPackaged;

// Get the correct paths for resources
function getResourcePath(relativePath) {
  if (isDev) {
    return path.join(__dirname, '..', '..', relativePath);
  }
  // In production, resources are in the app.asar or extraResources
  return path.join(process.resourcesPath, relativePath);
}

// Start the Python backend server
function startBackend() {
  return new Promise((resolve, reject) => {
    const backendPath = getResourcePath('backend');
    const pythonPath = isDev 
      ? 'python' // Use system Python in dev
      : path.join(process.resourcesPath, 'python', 'bin', 'python'); // Bundled Python in prod
    
    const configPath = isDev
      ? getResourcePath('config.local.yaml')
      : path.join(app.getPath('userData'), 'config.yaml');

    // Set ffmpeg path for the backend
    let ffmpegPath;
    if (isDev) {
      // In development, use system ffmpeg
      ffmpegPath = 'ffmpeg';
    } else {
      // In production, use bundled ffmpeg
      // On macOS, extraResources are in Contents/Resources/
      const bundledFfmpeg = path.join(process.resourcesPath, 'ffmpeg', 'ffmpeg');
      ffmpegPath = bundledFfmpeg;
      console.log('Using bundled ffmpeg at:', ffmpegPath);
    }

    // Copy default config if it doesn't exist in production
    if (!isDev && !fs.existsSync(configPath)) {
      const defaultConfig = path.join(process.resourcesPath, 'config.prod.yaml.example');
      if (fs.existsSync(defaultConfig)) {
        fs.copyFileSync(defaultConfig, configPath);
      }
    }

    const env = {
      ...process.env,
      CONFIG_PATH: configPath,
      PYTHONPATH: path.join(backendPath, 'src'),
      PORT: BACKEND_PORT.toString(),
      FFMPEG_PATH: ffmpegPath, // Add ffmpeg path to environment
      // Set data directory to user's writable location in production
      // In dev: backend/data, In prod: ~/Library/Application Support/tl-video-playground/data
      DATA_DIR: isDev ? path.join(backendPath, 'data') : path.join(app.getPath('userData'), 'data')
    };

    console.log('Starting backend server...');
    console.log('Backend path:', backendPath);
    console.log('Python path:', pythonPath);
    console.log('Config path:', configPath);
    console.log('FFmpeg path:', ffmpegPath);
    console.log('DATA_DIR:', env.DATA_DIR);

    const args = [
      '-m', 'uvicorn',
      'main:app',
      '--host', '127.0.0.1',
      '--port', BACKEND_PORT.toString(),
      '--log-level', 'info'
    ];

    // Set up log file for backend output (if enabled in config)
    let logStream = null;
    
    // Try to read config to check if file logging is enabled
    let fileLoggingEnabled = true; // Default to true
    try {
      if (fs.existsSync(configPath)) {
        const yaml = require('js-yaml');
        const configContent = fs.readFileSync(configPath, 'utf8');
        const config = yaml.load(configContent);
        if (config.logging && typeof config.logging.file_logging_enabled === 'boolean') {
          fileLoggingEnabled = config.logging.file_logging_enabled;
        }
      }
    } catch (error) {
      console.warn('Could not read logging config, defaulting to enabled:', error.message);
    }
    
    if (fileLoggingEnabled) {
      const logDir = isDev 
        ? path.join(backendPath, 'logs')
        : path.join(app.getPath('userData'), 'logs');
      
      // Create logs directory if it doesn't exist
      if (!fs.existsSync(logDir)) {
        fs.mkdirSync(logDir, { recursive: true });
      }
      
      const logFile = path.join(logDir, 'backend.log');
      logStream = fs.createWriteStream(logFile, { flags: 'a' });
      console.log('Backend logging to:', logFile);
    } else {
      console.log('File logging disabled in config');
    }

    // Run from backend/src directory to avoid circular import issues
    const backendSrcPath = path.join(backendPath, 'src');

    backendProcess = spawn(pythonPath, args, {
      cwd: backendSrcPath,
      env: env,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    backendProcess.stdout.on('data', (data) => {
      const message = data.toString();
      console.log(`Backend: ${message}`);
      if (logStream && !logStream.destroyed) {
        logStream.write(`[STDOUT] ${new Date().toISOString()} ${message}`);
      }
    });

    backendProcess.stderr.on('data', (data) => {
      const message = data.toString();
      console.error(`Backend Error: ${message}`);
      if (logStream && !logStream.destroyed) {
        logStream.write(`[STDERR] ${new Date().toISOString()} ${message}`);
      }
    });

    backendProcess.on('error', (error) => {
      console.error('Failed to start backend:', error);
      if (logStream && !logStream.destroyed) {
        logStream.write(`[ERROR] ${new Date().toISOString()} Failed to start: ${error}\n`);
        logStream.end();
      }
      reject(error);
    });

    backendProcess.on('exit', (code) => {
      console.log(`Backend process exited with code ${code}`);
      if (logStream && !logStream.destroyed) {
        logStream.write(`[EXIT] ${new Date().toISOString()} Process exited with code ${code}\n`);
        logStream.end();
      }
      if (code !== 0 && code !== null) {
        reject(new Error(`Backend exited with code ${code}`));
      }
    });

    // Wait for backend to be ready
    const maxAttempts = 30;
    let attempts = 0;
    
    const checkBackend = setInterval(async () => {
      attempts++;
      try {
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/health`);
        if (response.ok) {
          clearInterval(checkBackend);
          console.log('Backend is ready!');
          resolve();
        }
      } catch (error) {
        if (attempts >= maxAttempts) {
          clearInterval(checkBackend);
          reject(new Error('Backend failed to start within timeout'));
        }
      }
    }, 1000);
  });
}

// Stop the backend server
function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend server...');
    backendProcess.kill();
    backendProcess = null;
  }
}

// Create the main application window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
    },
    icon: path.join(__dirname, 'icon.png'),
    show: false // Don't show until ready
  });

  // Load the frontend
  if (isDev) {
    // In development, load from Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load from built files in app.asar
    const distPath = path.join(__dirname, '..', 'dist');
    const indexPath = path.join(distPath, 'index.html');
    
    mainWindow.loadFile(indexPath).catch(err => {
      console.error('Failed to load index.html:', err);
    });
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(async () => {
  try {
    // Start backend first
    await startBackend();
    
    // Then create window
    createWindow();
  } catch (error) {
    console.error('Failed to start application:', error);
    app.quit();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

// IPC handlers
ipcMain.handle('get-backend-url', () => {
  return `http://127.0.0.1:${BACKEND_PORT}`;
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-config-path', () => {
  return isDev 
    ? getResourcePath('config.local.yaml')
    : path.join(app.getPath('userData'), 'config.yaml');
});
