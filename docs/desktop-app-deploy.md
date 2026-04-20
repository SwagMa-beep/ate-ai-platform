# Desktop App Deployment (Windows)

This project now supports a desktop wrapper using Electron.

## 1) Prerequisites

- Node.js 20+ (recommended)
- Python 3.10+
- Backend dependencies installed:

```powershell
cd backend
pip install -r ..\requirements.txt
```

> The Electron app starts FastAPI automatically with `python -m uvicorn app.main:app`.
> If Python is not in `PATH`, set `PYTHON_PATH` before running.

## 2) Install frontend/electron dependencies

```powershell
cd apps
npm install
```

## 3) Run desktop app in development mode

```powershell
cd apps
npm run desktop:dev
```

What this does:

- starts Vite dev server at `http://127.0.0.1:3000`
- starts FastAPI backend at `http://127.0.0.1:8000`
- opens Electron window

## 4) Build desktop package (Windows)

```powershell
cd apps
npm run desktop:build
```

This produces a packaged Windows app under `apps/release/` (unpacked app folder).

## 5) Build Windows installer (.exe setup)

```powershell
cd apps
$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://npmmirror.com/mirrors/electron-builder-binaries/'
npm run desktop:installer
```

Installer output:

- `apps/release-installer/ATE-AI-Platform-Setup-<version>.exe`

## 6) Runtime notes

- Frontend uses relative API calls in web mode.
- In packaged desktop mode (`file://`), frontend auto-switches API origin to `http://127.0.0.1:8000`.
- Backend source is bundled into app resources as `backend`.
