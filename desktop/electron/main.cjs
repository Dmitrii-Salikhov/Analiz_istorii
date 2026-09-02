const { app, BrowserWindow, dialog, ipcMain, shell, session } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { PythonBridge } = require('./pythonBridge.cjs');
const { bindApplicationMenu, syncMenuState } = require('./appMenu.cjs');
const {
  approvePath,
  approveLoadPaths,
  assertRpcMethod,
  gateRpcParams,
  assertSafeExternalUrl,
  assertApprovedOpenPath,
} = require('./bridgeSecurity.cjs');

/** @type {BrowserWindow | null} */
let mainWindow = null;
const bridge = new PythonBridge();

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

function applyCsp() {
  const isDev = !!process.env.VITE_DEV_SERVER_URL;
  const csp = isDev
    ? "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' data:; frame-src 'self' blob: data: file:; connect-src 'self' ws://127.0.0.1:* http://127.0.0.1:* ws://localhost:* http://localhost:*; object-src 'none'; base-uri 'self';"
    : "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; frame-src 'self' blob: data: file:; connect-src 'self'; object-src 'none'; base-uri 'self';";

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const headers = { ...details.responseHeaders };
    headers['Content-Security-Policy'] = [csp];
    callback({ responseHeaders: headers });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#0c0e12',
    title: 'Анализ работы отделения',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    mainWindow.loadURL(devUrl);
    if (process.env.ANALIZ_DEVTOOLS === '1') {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  try {
    bindApplicationMenu(mainWindow, bridge.projectRoot());
  } catch {
    bindApplicationMenu(mainWindow, '');
  }
}

/** @type {Map<string, { buffer: Buffer, createdAt: number }>} */
const pdfCache = new Map();
const PDF_CACHE_TTL_MS = 30 * 60 * 1000;

function purgePdfCache() {
  const now = Date.now();
  for (const [id, entry] of pdfCache.entries()) {
    if (now - entry.createdAt > PDF_CACHE_TTL_MS) {
      pdfCache.delete(id);
    }
  }
}

function storePdfBuffer(buffer) {
  purgePdfCache();
  const id = `pdf-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  pdfCache.set(id, { buffer, createdAt: Date.now() });
  return id;
}

function takePdfBuffer(id) {
  const entry = pdfCache.get(String(id || ''));
  if (!entry) {
    throw new Error('PDF не найден — обновите предпросмотр');
  }
  return entry.buffer;
}

async function renderHtmlToPdfBuffer(html, landscape) {
  const htmlPath = path.join(
    app.getPath('temp'),
    `analiz-html-${process.pid}-${Date.now()}.html`,
  );
  fs.writeFileSync(htmlPath, html, 'utf8');

  /** @type {import('electron').BrowserWindow | null} */
  let renderWin = null;

  try {
    renderWin = new BrowserWindow({
      show: false,
      webPreferences: {
        sandbox: true,
        nodeIntegration: false,
        contextIsolation: true,
      },
    });
    await renderWin.loadFile(htmlPath);
    await new Promise((resolve) => setTimeout(resolve, 150));
    const data = await renderWin.webContents.printToPDF({
      printBackground: true,
      landscape: !!landscape,
      pageSize: 'A4',
      margins: {
        marginType: 'custom',
        top: 0.35,
        bottom: 0.45,
        left: 0.35,
        right: 0.35,
      },
    });
    return Buffer.from(data);
  } finally {
    if (renderWin && !renderWin.isDestroyed()) {
      renderWin.destroy();
    }
    try {
      fs.unlinkSync(htmlPath);
    } catch {
      // ignore
    }
  }
}

function registerIpc() {
  ipcMain.handle('bridge:rpc', async (_e, method, params) => {
    const m = assertRpcMethod(method);
    const gated = gateRpcParams(m, params || {});
    const result = await bridge.rpc(m, gated);
    // Export may return a resolved path — allow opening it afterwards
    if ((m === 'emk.export' || m === 'ksg.export' || m === 'ops.export') && result && result.path) {
      approvePath(String(result.path));
    }
    return result;
  });

  ipcMain.handle('bridge:status', async () => {
    try {
      await bridge.ensureStarted();
      return bridge.status();
    } catch (e) {
      return { ok: false, detail: e instanceof Error ? e.message : String(e) };
    }
  });

  ipcMain.handle('app:getVersion', async () => {
    try {
      const root = bridge.projectRoot();
      const vf = path.join(root, 'version.txt');
      if (fs.existsSync(vf)) return fs.readFileSync(vf, 'utf8').trim();
    } catch {
      // ignore
    }
    return app.getVersion();
  });

  ipcMain.handle('paths:approveLoad', async (_e, paths) => {
    const list = Array.isArray(paths) ? paths : paths ? [paths] : [];
    return approveLoadPaths(list);
  });

  ipcMain.handle('dialog:openExcel', async (_e, opts = {}) => {
    const multi = !!opts.multiSelections;
    const res = await dialog.showOpenDialog(mainWindow, {
      title: opts.title || 'Выберите файл Excel',
      properties: multi ? ['openFile', 'multiSelections'] : ['openFile'],
      filters: [{ name: 'Excel', extensions: ['xlsx', 'xls'] }],
    });
    if (res.canceled || !res.filePaths.length) return multi ? [] : null;
    const approved = approveLoadPaths(res.filePaths);
    return multi ? approved : approved[0] || null;
  });

  ipcMain.handle('dialog:saveExcel', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить Excel',
      defaultPath: opts.defaultPath || 'report.xlsx',
      filters: [{ name: 'Excel', extensions: ['xlsx'] }],
    });
    if (res.canceled || !res.filePath) return null;
    return approvePath(res.filePath);
  });

  ipcMain.handle('dialog:saveText', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить TXT',
      defaultPath: opts.defaultPath || 'report.txt',
      filters: [{ name: 'Text', extensions: ['txt'] }],
    });
    if (res.canceled || !res.filePath) return null;
    return approvePath(res.filePath);
  });

  ipcMain.handle('shell:openPath', async (_e, filePath) => {
    const p = assertApprovedOpenPath(filePath);
    return shell.openPath(p);
  });

  ipcMain.handle('shell:openExternal', async (_e, url) => {
    const safe = assertSafeExternalUrl(url);
    await shell.openExternal(safe);
  });

  ipcMain.handle('menu:sync', async (_e, state) => {
    syncMenuState(state || {});
    return { ok: true };
  });

  ipcMain.handle('pdf:fromHtml', async (_e, opts = {}) => {
    const html = String(opts.html || '');
    if (!html.trim()) {
      throw new Error('Пустой документ для PDF');
    }
    if (html.length > 8_000_000) {
      throw new Error('Документ слишком большой для PDF');
    }
    const landscape = !!opts.landscape;
    const buffer = await renderHtmlToPdfBuffer(html, landscape);
    const id = storePdfBuffer(buffer);
    return {
      id,
      byteLength: buffer.length,
    };
  });

  ipcMain.handle('pdf:release', async (_e, id) => {
    if (id) pdfCache.delete(String(id));
    return { ok: true };
  });

  ipcMain.handle('pdf:save', async (_e, opts = {}) => {
    const buffer = takePdfBuffer(opts.id);
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить PDF',
      defaultPath: opts.defaultPath || 'Печать_операции.pdf',
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (res.canceled || !res.filePath) return null;
    const target = approvePath(res.filePath);
    fs.writeFileSync(target, buffer);
    if (opts.openAfterSave) {
      const openErr = await shell.openPath(target);
      if (openErr) {
        throw new Error(openErr);
      }
    }
    if (opts.revealInFolder) {
      shell.showItemInFolder(target);
    }
    return target;
  });
}

app.whenReady().then(async () => {
  if (process.platform === 'darwin') {
    app.setName('Анализ работы отделения');
  }
  applyCsp();
  registerIpc();
  createWindow();
  try {
    await bridge.ensureStarted();
  } catch (e) {
    console.error('[bridge] failed to start', e);
  }
});

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.on('window-all-closed', () => {
  bridge.stop();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  bridge.stop();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
