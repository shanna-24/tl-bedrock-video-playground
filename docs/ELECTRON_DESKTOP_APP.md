# Electron Desktop App Guide

This guide covers building, packaging, and distributing the TL-Video-Playground as a standalone desktop application for macOS, Windows, and Linux.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Building the App](#building-the-app)
- [Installation Guide](#installation-guide)
- [Troubleshooting](#troubleshooting)
- [Distribution](#distribution)

---

## Overview

The Electron desktop app bundles:
- React frontend (built with Vite)
- Python FastAPI backend (with all dependencies)
- Standalone Python runtime
- Configuration files

Users get a single installable application that runs completely standalone (except for AWS credentials).

### Architecture

```
Electron App
├── Main Process (Node.js)
│   ├── Starts Python backend server (localhost:8000)
│   ├── Sets FFMPEG_PATH environment variable
│   ├── Creates application window
│   └── Manages app lifecycle
├── Renderer Process (React)
│   └── Communicates with backend via REST API
├── Python Backend (FastAPI)
│   ├── Bundled Python runtime
│   ├── All pip dependencies
│   └── Backend source code
└── FFmpeg Binary
    └── Used for video processing and thumbnail generation
```

### Build Output

- **macOS**: `.dmg` installer and `.zip` portable (~190 MB)
- **Windows**: `.exe` installer and portable (~200 MB)
- **Linux**: `.AppImage` and `.deb` packages (~250 MB)

The app bundles:
- Python runtime with all dependencies
- FFmpeg binary for video processing
- React frontend
- FastAPI backend

---

## Quick Start

### Development Mode

Run the app in development with hot reload:

```bash
# Start Vite dev server and Electron
./scripts/dev-electron.sh

# Or manually:
cd frontend
npm run electron:dev
```

### Production Build

Build the complete desktop app:

```bash
# All-in-one build script
./scripts/package-electron.sh

# Or step-by-step:
./scripts/build-python-bundle.sh  # Build Python runtime
cd frontend
npm run build                      # Build React frontend
npm run electron:build             # Package Electron app
```

Output: `frontend/dist-electron/`

---

## Building the App

### Prerequisites

**All Platforms:**
- Node.js 20+
- Python 3.11+
- Git

**macOS:**
```bash
xcode-select --install
brew install python@3.11
```

**Windows:**
- Install Python from python.org
- Install Visual Studio Build Tools
- Install Node.js from nodejs.org

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip nodejs npm
```

### Build Process

#### Step 1: Install Dependencies

```bash
# Frontend dependencies
cd frontend
npm install

# Backend dependencies (for bundling)
cd ../backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
deactivate
```

#### Step 2: Build Python Bundle

Creates a standalone Python environment with all dependencies:

```bash
./scripts/build-python-bundle.sh
```

This creates `build/python-bundle/` containing:
- Python runtime
- All pip packages from requirements.txt
- Isolated from system Python

**Note**: Build on the target platform (macOS bundle for macOS, etc.)

#### Step 3: Build Frontend

```bash
cd frontend
npm run build
```

Creates `frontend/dist/` with the production React build.

#### Step 4: Package Electron App

```bash
cd frontend
npm run electron:build
```

Or use the all-in-one script:

```bash
./scripts/package-electron.sh
```

### Platform-Specific Builds

**macOS:**
```bash
# On macOS machine
./scripts/package-electron.sh
# Output: .dmg and .zip files
```

**Windows:**
```bash
# On Windows machine
.\scripts\package-electron.sh
# Output: .exe installer and portable .exe
```

**Linux:**
```bash
# On Linux machine
./scripts/package-electron.sh
# Output: .AppImage and .deb files
```

---

## Installation Guide

### For End Users

#### macOS Installation

1. **Download** `TL-Video-Playground-1.0.0-arm64.dmg`
2. **Open** the DMG file
3. **Drag** the app to Applications folder
4. **First launch**: Right-click → "Open" (not double-click)
5. Click "Open" in the security dialog

**Data Storage Location:**
- Config: `~/Library/Application Support/TL-Video-Playground/config.yaml`
- Data: `~/Library/Application Support/TL-Video-Playground/data/`
  - `indexes.json` - Video index metadata
  - `embedding_jobs.json` - Background job tracking

#### Windows Installation

1. **Download** `TL-Video-Playground Setup 1.0.0.exe`
2. **Run** the installer
3. Follow the installation wizard
4. If SmartScreen appears: "More info" → "Run anyway"

**Data Storage Location:**
- Config: `%APPDATA%\TL-Video-Playground\config.yaml`
- Data: `%APPDATA%\TL-Video-Playground\data\`
  - `indexes.json` - Video index metadata
  - `embedding_jobs.json` - Background job tracking

#### Linux Installation

**AppImage (No Installation):**
```bash
chmod +x TwelveLabs\ Video\ Archive-1.0.0.AppImage
./TwelveLabs\ Video\ Archive-1.0.0.AppImage
```

**Debian/Ubuntu:**
```bash
sudo dpkg -i tl-video-playground_1.0.0_amd64.deb
sudo apt-get install -f  # Install dependencies if needed
```

**Data Storage Location:**
- Config: `~/.config/TL-Video-Playground/config.yaml`
- Data: `~/.config/TL-Video-Playground/data/`
  - `indexes.json` - Video index metadata
  - `embedding_jobs.json` - Background job tracking

### Configuration

#### Data Storage

The Electron app stores all user data in the operating system's standard application data directory:

- **macOS**: `~/Library/Application Support/TL-Video-Playground/`
- **Windows**: `%APPDATA%\TL-Video-Playground\`
- **Linux**: `~/.config/TL-Video-Playground/`

This includes:
- `config.yaml` - Application configuration
- `data/indexes.json` - Video index metadata
- `data/embedding_jobs.json` - Background job tracking

**Important:** The Electron app's data is completely separate from:
- Browser-based development (uses `backend/data/`)
- AWS production deployment (uses its own data directory)

Each environment maintains its own isolated state and S3 buckets.

#### Locate Config File

On first launch, the app creates a config file:

- **macOS**: `~/Library/Application Support/TL-Video-Playground/config.yaml`
- **Windows**: `%APPDATA%\TL-Video-Playground\config.yaml`
- **Linux**: `~/.config/TL-Video-Playground/config.yaml`

#### Set AWS Credentials

**Method A: Environment Variables (Recommended)**

macOS/Linux - Add to `~/.zshrc` or `~/.bash_profile`:
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

Windows - Set in System Environment Variables:
1. Search "Environment Variables" in Start menu
2. Add user variables:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_DEFAULT_REGION`

**Method B: AWS Credentials File**

Create `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
```

And `~/.aws/config`:
```ini
[default]
region = us-east-1
```

#### Edit Configuration

Open the config file and update:

```yaml
# AWS Configuration
aws:
  region: "us-east-1"
  bedrock:
    marengo_model_id: "amazon.marengo-v1"
    pegasus_model_id: "amazon.pegasus-v1"

# Authentication
auth:
  password: "your-secure-password"  # Change this!
  jwt_secret: "your-secret-key"     # Change this!

# Storage
storage:
  s3_bucket: "your-bucket-name"
  s3_vectors_bucket: "your-vectors-bucket"
```

Restart the app after making changes.

#### Upload Compliance Configuration (Optional)

The compliance configuration files are automatically uploaded to S3 on first startup if they don't already exist. The app checks for these files in `backend/compliance_config/` and uploads them to `s3://your-bucket/compliance/configuration/`.

If you want to customize the compliance rules before first run, edit the files in `backend/compliance_config/` before starting the app. Or manually upload custom configs:

```bash
# From the project root directory
./scripts/upload-compliance-config.sh your-bucket-name us-east-1
```

The compliance config files include:
- `compliance_params.json` - Company and product parameters
- `moral_standards_check.json` - Moral standards compliance rules
- `video_content_check.json` - Video content compliance rules
- `content_relevance_check.json` - Content relevance pre-check config (optional)

---

## Troubleshooting

### App Won't Start

**macOS: "App is damaged"**
```bash
xattr -cr "/Applications/TL-Video-Playground.app"
```

**Windows: SmartScreen Warning**
- Click "More info" → "Run anyway"

**Linux: Permission Denied**
```bash
chmod +x TwelveLabs\ Video\ Archive-1.0.0.AppImage
```

### Connection Errors

**"Failed to connect to backend"**
1. Check if port 8000 is available: `lsof -i :8000` (macOS/Linux)
2. Check firewall settings
3. Look at app logs (see below)

**"AWS credentials not found"**
1. Verify environment variables are set
2. Check `~/.aws/credentials` file exists
3. Restart the app after setting credentials

### Upload Failures

**"Failed to upload video"**
1. Check video format (MP4, MOV, AVI, MKV supported)
2. Check video size (max 5 GB recommended)
3. Verify S3 bucket exists and is accessible
4. Check AWS credentials have S3 write permissions

### Application Logs

**macOS:**
```bash
~/Library/Logs/TL-Video-Playground/main.log
~/Library/Application Support/TL-Video-Playground/backend.log
```

**Windows:**
```
%APPDATA%\TL-Video-Playground\logs\main.log
%APPDATA%\TL-Video-Playground\backend.log
```

**Linux:**
```bash
~/.config/TL-Video-Playground/logs/main.log
~/.config/TL-Video-Playground/backend.log
```

### Common Issues

#### White Screen on Launch

**Fixed in current version**. If you encounter this:
- Ensure `base: './'` is set in `frontend/vite.config.ts`
- Rebuild the app

#### ES Module Error

**Fixed in current version**. Electron files use `.cjs` extension for CommonJS compatibility.

#### Backend Fails to Start

1. Check Python bundle exists in app Resources
2. Verify port 8000 is available
3. Check backend logs for errors
4. Ensure config.yaml is valid

---

## Distribution

### Adding a Custom Icon

The app currently uses the default Electron icon. To add your own:

1. **Create a 512x512 PNG icon**
2. **Save as** `frontend/electron/icon.png`
3. **Update** `frontend/package.json`:

```json
{
  "build": {
    "mac": {
      "icon": "electron/icon.png"
    },
    "win": {
      "icon": "electron/icon.png"
    },
    "linux": {
      "icon": "electron/icon.png"
    }
  }
}
```

4. **Rebuild** the app

For platform-specific formats:
- **macOS**: Convert to `.icns` using `iconutil`
- **Windows**: Convert to `.ico` using ImageMagick or online tools

### Code Signing

#### macOS

Requires Apple Developer account:

```bash
# Sign the app
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  "TL-Video-Playground.app"

# Verify signature
codesign --verify --deep --strict --verbose=2 \
  "TL-Video-Playground.app"

# Notarize (for Gatekeeper)
xcrun notarytool submit "TL-Video-Playground-1.0.0-arm64.dmg" \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --password "app-specific-password"

# Staple ticket
xcrun stapler staple "TL-Video-Playground.app"
```

#### Windows

Requires code signing certificate:

```bash
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com "TL-Video-Playground.exe"
```

### Distribution Checklist

- [ ] Test on clean machine
- [ ] Add custom icon
- [ ] Code sign (optional but recommended)
- [ ] Create release notes
- [ ] Prepare installation guide
- [ ] Upload to distribution server
- [ ] Test download links
- [ ] Provide user documentation

### Auto-Updates (Optional)

To add auto-update functionality:

1. **Install electron-updater**:
```bash
cd frontend
npm install electron-updater
```

2. **Set up update server** (GitHub Releases, S3, or custom)

3. **Add update logic** to `frontend/electron/main.cjs`

See: https://www.electron.build/auto-update

---

## Technical Details

### File Structure

```
tl-video-playground/
├── frontend/
│   ├── electron/              # Electron main process
│   │   ├── main.cjs          # App entry point
│   │   ├── preload.cjs       # IPC bridge
│   │   └── entitlements.mac.plist
│   ├── src/                  # React app
│   │   └── services/
│   │       └── electron.ts   # Electron API wrapper
│   └── package.json          # Electron build config
├── backend/                  # Python FastAPI backend
├── scripts/
│   ├── build-python-bundle.sh
│   ├── package-electron.sh
│   └── dev-electron.sh
└── build/
    └── python-bundle/        # Bundled Python runtime
```

### Configuration Files

**`frontend/package.json`** - Electron build configuration:
```json
{
  "main": "electron/main.cjs",
  "build": {
    "appId": "com.twelvelabs.videoarchive",
    "files": ["dist/**/*", "electron/**/*"],
    "extraResources": [
      {"from": "../backend", "to": "backend"},
      {"from": "../build/python-bundle", "to": "python"}
    ]
  }
}
```

**`frontend/vite.config.ts`** - Vite configuration:
```typescript
export default defineConfig({
  plugins: [react()],
  base: './',  // Required for Electron file:// protocol
})
```

### Build Commands

```bash
# Development
./scripts/dev-electron.sh

# Build Python bundle
./scripts/build-python-bundle.sh

# Build frontend
cd frontend && npm run build

# Package app
cd frontend && npm run electron:build

# Full build
./scripts/package-electron.sh

# Clean build artifacts
rm -rf frontend/dist frontend/dist-electron build/python-bundle
```

### Size Breakdown

```
Total App:           ~330 MB (uncompressed)
├── Python Runtime:   324 MB (includes all pip packages)
├── Frontend:          11 MB (React app in app.asar)
├── Backend:          4.6 MB (Python source code)
└── Electron:          ~5 MB (framework)

Compressed (DMG):    ~190 MB
```

---

## Resources

- [Electron Documentation](https://www.electronjs.org/docs)
- [electron-builder Documentation](https://www.electron.build/)
- [Vite Documentation](https://vitejs.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Summary

The Electron desktop app provides a complete standalone experience:
- ✅ Single installer for end users
- ✅ No separate backend setup required
- ✅ Bundled Python runtime
- ✅ Cross-platform support (macOS, Windows, Linux)
- ✅ Automatic backend startup
- ✅ Native app experience

For questions or issues, refer to the troubleshooting section or check the application logs.
