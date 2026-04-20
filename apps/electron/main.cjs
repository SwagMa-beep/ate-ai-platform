const { app, BrowserWindow, dialog } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

let backendProcess = null;
let mainWindow = null;
const PORT_RANGE_START = Number(process.env.ATE_BACKEND_PORT_START || 18080);
const PORT_RANGE_SIZE = 100;
const PORT_RANGE_END = PORT_RANGE_START + PORT_RANGE_SIZE - 1;
let backendPort = PORT_RANGE_START;
let backendWasSpawnedByApp = false;
let isBootstrapping = true;
let backendLaunchToken = 0;
let backendInfo = {
  pythonBin: '',
  args: [],
  stdoutTail: '',
  stderrTail: '',
};

function getBackendPidFile() {
  return path.join(app.getPath('userData'), 'backend.pid');
}

function appendTail(prev, chunk) {
  const maxLen = 3000;
  const merged = `${prev}${chunk}`;
  if (merged.length <= maxLen) return merged;
  return merged.slice(merged.length - maxLen);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isPortConflictMessage(message) {
  const text = String(message || '').toLowerCase();
  return (
    text.includes('10048') ||
    text.includes('address already in use') ||
    text.includes('error while attempting to bind') ||
    text.includes('only one usage of each socket address')
  );
}

function getRepoRootDir() {
  return path.join(__dirname, '..', '..');
}

function getBackendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend');
  }
  return path.join(getRepoRootDir(), 'backend');
}

function readTextFileIfExists(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return null;
  }
}

function clearBackendPidFile() {
  try {
    fs.unlinkSync(getBackendPidFile());
  } catch {
    // ignore
  }
}

function saveBackendPidFile(pid) {
  try {
    fs.writeFileSync(getBackendPidFile(), String(pid), 'utf8');
  } catch {
    // ignore
  }
}

function getProcessCommandLine(pid) {
  try {
    const probe = spawnSync(
      'powershell.exe',
      [
        '-NoProfile',
        '-Command',
        `(Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}").CommandLine`,
      ],
      { encoding: 'utf8', windowsHide: true }
    );
    if (probe.status !== 0) return '';
    return (probe.stdout || '').trim();
  } catch {
    return '';
  }
}

function cleanupStaleBackendProcess() {
  const pidText = readTextFileIfExists(getBackendPidFile());
  if (!pidText) return;
  const pid = Number(pidText.trim());
  if (!Number.isInteger(pid) || pid <= 0) {
    clearBackendPidFile();
    return;
  }

  const cmd = getProcessCommandLine(pid);
  if (!cmd || !cmd.includes('uvicorn') || !cmd.includes('app.main:app')) {
    clearBackendPidFile();
    return;
  }

  try {
    process.kill(pid);
  } catch {
    // ignore if already gone
  }
  clearBackendPidFile();
}

function isPythonAvailable(bin, probeArgs) {
  const probe = spawnSync(bin, probeArgs, { stdio: 'ignore' });
  return probe.status === 0;
}

function resolvePythonCommand() {
  const candidates = [];
  if (process.env.PYTHON_PATH) {
    candidates.push({ bin: process.env.PYTHON_PATH, prefix: [], probe: ['-c', 'print(1)'] });
  }

  // Prefer project virtualenv during local development.
  const venvPython = path.join(getRepoRootDir(), '.venv', 'Scripts', 'python.exe');
  candidates.push({ bin: venvPython, prefix: [], probe: ['-c', 'print(1)'] });

  // Fallback to system python launchers.
  candidates.push({ bin: 'python', prefix: [], probe: ['-c', 'print(1)'] });
  candidates.push({ bin: 'py', prefix: ['-3'], probe: ['-3', '-c', 'print(1)'] });

  for (const candidate of candidates) {
    if (isPythonAvailable(candidate.bin, candidate.probe)) {
      return candidate;
    }
  }
  return null;
}

async function isPortFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, '127.0.0.1');
  });
}

async function isHealthyAtPort(port) {
  try {
    const resp = await fetch(`http://127.0.0.1:${port}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}

async function isAteBackendAtPort(port) {
  try {
    const resp = await fetch(`http://127.0.0.1:${port}/health`);
    if (!resp.ok) return false;
    const payload = await resp.json().catch(() => null);
    return Boolean(payload && payload.status === 'success' && payload.data && payload.data.version);
  } catch {
    return false;
  }
}

async function findReusableBackendPort() {
  for (let port = PORT_RANGE_START; port <= PORT_RANGE_END; port += 1) {
    if (await isAteBackendAtPort(port)) return port;
  }
  return null;
}

async function startBackendWithAutoPort() {
  const candidatePorts = Array.from({ length: PORT_RANGE_SIZE }, (_, i) => PORT_RANGE_START + i);
  let lastError = null;

  for (const candidate of candidatePorts) {
    if (!(await isPortFree(candidate))) {
      continue;
    }

    backendPort = candidate;
    backendWasSpawnedByApp = true;
    startBackend(candidate);
    try {
      await waitForBackendReady();
      return;
    } catch (err) {
      lastError = err;
      const message = String(err instanceof Error ? err.message : err);
      if (await isAteBackendAtPort(candidate)) {
        backendPort = candidate;
        backendWasSpawnedByApp = false;
        await stopCurrentBackendProcess();
        return;
      }

      const portStillFree = await isPortFree(candidate);
      await stopCurrentBackendProcess();
      if (isPortConflictMessage(message) || !portStillFree) {
        continue;
      }
      throw err;
    }
  }

  if (lastError) throw lastError;
  throw new Error(`No usable local port found in range ${PORT_RANGE_START}-${PORT_RANGE_END} for backend.`);
}

function startBackend(port) {
  const backendDir = getBackendDir();
  const python = resolvePythonCommand();
  if (!python) {
    throw new Error(
      'Python runtime not found. Install Python 3.10+ or set PYTHON_PATH to python.exe.'
    );
  }

  const args = [
    ...python.prefix,
    '-m',
    'uvicorn',
    'app.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    String(port),
  ];
  backendInfo.pythonBin = python.bin;
  backendInfo.args = args;
  backendInfo.stdoutTail = '';
  backendInfo.stderrTail = '';
  backendLaunchToken += 1;
  const launchToken = backendLaunchToken;

  backendProcess = spawn(python.bin, args, {
    cwd: backendDir,
    stdio: 'pipe',
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
    },
  });
  const childPid = backendProcess.pid;
  saveBackendPidFile(backendProcess.pid);

  backendProcess.on('error', (err) => {
    if (launchToken !== backendLaunchToken) return;
    dialog.showErrorBox(
      'Backend start failed',
      `Unable to start FastAPI backend with command "${python.bin}".\n${String(err)}`
    );
    app.quit();
  });

  backendProcess.stdout.on('data', (chunk) => {
    if (launchToken !== backendLaunchToken) return;
    const text = chunk.toString();
    backendInfo.stdoutTail = appendTail(backendInfo.stdoutTail, text);
    process.stdout.write(`[backend] ${text}`);
  });
  backendProcess.stderr.on('data', (chunk) => {
    if (launchToken !== backendLaunchToken) return;
    const text = chunk.toString();
    backendInfo.stderrTail = appendTail(backendInfo.stderrTail, text);
    process.stderr.write(`[backend] ${text}`);
  });

  backendProcess.on('exit', (code) => {
    clearBackendPidFile();
    if (backendProcess && backendProcess.pid === childPid) {
      backendProcess = null;
    }
    if (launchToken !== backendLaunchToken) return;
    if (!app.isQuitting && backendWasSpawnedByApp && !isBootstrapping) {
      const details = backendInfo.stderrTail || backendInfo.stdoutTail || 'No backend output captured.';
      dialog.showErrorBox(
        'Backend exited',
        `FastAPI backend stopped unexpectedly (code: ${code ?? 'unknown'}).\n\n` +
        `Last output:\n${details}`
      );
      app.quit();
    }
  });
}

async function waitForBackendReady() {
  const maxTries = 180; // 90s, backend may need extra init time
  for (let i = 0; i < maxTries; i += 1) {
    if (backendProcess && backendProcess.exitCode !== null) {
      await sleep(300);
      if (await isAteBackendAtPort(backendPort)) return;
      const details = backendInfo.stderrTail || backendInfo.stdoutTail || 'No backend output captured.';
      throw new Error(
        `Backend process exited early (code: ${backendProcess.exitCode}).\n` +
        `Command: ${backendInfo.pythonBin} ${backendInfo.args.join(' ')}\n\n` +
        `Last output:\n${details}`
      );
    }
    try {
      const resp = await fetch(`http://127.0.0.1:${backendPort}/health`);
      if (resp.ok) return;
    } catch {
      // wait and retry
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  const details = backendInfo.stderrTail || backendInfo.stdoutTail || 'No backend output captured.';
  throw new Error(
    `Backend failed to become ready on http://127.0.0.1:${backendPort}/health within 90 seconds.\n\n` +
    `Command: ${backendInfo.pythonBin} ${backendInfo.args.join(' ')}\n\n` +
    `Last output:\n${details}`
  );
}

async function stopCurrentBackendProcess() {
  const proc = backendProcess;
  if (!proc) return;
  backendLaunchToken += 1;
  backendProcess = null;
  try {
    if (proc.exitCode === null) {
      proc.kill();
    }
  } catch {
    // ignore cleanup failures
  }
}

async function loadRenderer(mainWindow) {
  const apiOrigin = `http://127.0.0.1:${backendPort}`;
  const devUrl = process.env.ELECTRON_RENDERER_URL;
  if (devUrl) {
    const url = new URL(devUrl);
    url.searchParams.set('apiOrigin', apiOrigin);
    await mainWindow.loadURL(url.toString());
    mainWindow.webContents.openDevTools({ mode: 'detach' });
    return;
  }

  const indexPath = path.join(__dirname, '..', 'dist', 'index.html');
  const fileUrl = pathToFileURL(indexPath);
  fileUrl.searchParams.set('apiOrigin', apiOrigin);
  await mainWindow.loadURL(fileUrl.toString());
}

async function loadRendererWithRetry(mainWindow) {
  let lastError = null;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      await loadRenderer(mainWindow);
      return;
    } catch (err) {
      lastError = err;
      if (attempt === 2) break;
      await sleep(500);
    }
  }
  throw lastError;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1120,
    minHeight: 720,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await loadRendererWithRetry(mainWindow);
  const apiOrigin = `http://127.0.0.1:${backendPort}`;
  mainWindow.webContents.once('did-finish-load', () => {
    mainWindow.webContents.executeJavaScript(
      `
        try { sessionStorage.setItem('ate_api_origin', ${JSON.stringify(apiOrigin)}); } catch {}
        try { localStorage.setItem('ate_api_origin', ${JSON.stringify(apiOrigin)}); } catch {}
      `,
      true
    ).catch(() => {});
  });
}

async function bootstrap() {
  try {
    cleanupStaleBackendProcess();
    const reusablePort = await findReusableBackendPort();
    if (reusablePort !== null) {
      backendPort = reusablePort;
      backendWasSpawnedByApp = false;
    } else {
      await startBackendWithAutoPort();
    }
    isBootstrapping = false;
    await createWindow();
  } catch (err) {
    dialog.showErrorBox(
      'Desktop app startup failed',
      err instanceof Error ? err.message : String(err)
    );
    app.quit();
  }
}

app.on('before-quit', () => {
  app.isQuitting = true;
  if (backendProcess && backendWasSpawnedByApp) {
    backendProcess.kill();
  }
});

app.whenReady().then(bootstrap);

app.on('window-all-closed', () => {
  app.quit();
});
