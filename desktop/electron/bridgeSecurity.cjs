/**
 * Security helpers for Electron main ↔ Python bridge.
 * Session-scoped path allowlist + RPC method gate.
 */
const path = require('node:path');
const fs = require('node:fs');

const ALLOWED_RPC = new Set([
  'ping',
  'app.version',
  'config.get',
  'config.set',
  'ref.operations',
  'ref.departments',
  'emk.load',
  'emk.analyze',
  'emk.export',
  'emk.sections',
  'emk.violationsSummary',
  'ksg.load',
  'ksg.list',
  'ksg.setActive',
  'ksg.remove',
  'ksg.reanalyze',
  'ksg.compare',
  'ksg.export',
]);

const LOAD_METHODS = new Set(['emk.load', 'ksg.load']);
const EXPORT_METHODS = new Set(['emk.export', 'ksg.export']);

const EXCEL_EXT = new Set(['.xlsx', '.xls', '.xlsm']);
const EXPORT_EXT = new Set(['.xlsx', '.txt']);

/** @type {Set<string>} */
const approvedPaths = new Set();

function normalizePath(filePath) {
  return path.resolve(String(filePath || '').trim());
}

function approvePath(filePath) {
  const p = normalizePath(filePath);
  if (!p) throw new Error('Пустой путь');
  approvedPaths.add(p);
  return p;
}

function approvePaths(paths) {
  if (!Array.isArray(paths)) return [];
  return paths.filter(Boolean).map((p) => approvePath(p));
}

function isApproved(filePath) {
  return approvedPaths.has(normalizePath(filePath));
}

function assertApprovedPath(filePath, kind) {
  const p = normalizePath(filePath);
  if (!isApproved(p)) {
    throw new Error(
      kind === 'export'
        ? 'Путь сохранения не подтверждён (нужен диалог «Сохранить»)'
        : 'Путь файла не подтверждён (нужен диалог или drag-and-drop)',
    );
  }
  return p;
}

function assertExcelPath(filePath) {
  const p = normalizePath(filePath);
  const ext = path.extname(p).toLowerCase();
  if (!EXCEL_EXT.has(ext)) {
    throw new Error('Разрешены только файлы Excel (.xlsx / .xls)');
  }
  if (!fs.existsSync(p) || !fs.statSync(p).isFile()) {
    throw new Error(`Файл не найден: ${p}`);
  }
  return p;
}

function assertExportPath(filePath) {
  const p = normalizePath(filePath);
  const ext = path.extname(p).toLowerCase();
  if (!EXPORT_EXT.has(ext)) {
    throw new Error('Разрешены только .xlsx или .txt');
  }
  const parent = path.dirname(p);
  if (!fs.existsSync(parent) || !fs.statSync(parent).isDirectory()) {
    throw new Error(`Папка не найдена: ${parent}`);
  }
  return p;
}

/**
 * Approve a dropped/selected Excel path after existence + extension checks.
 * @param {string[]} paths
 */
function approveLoadPaths(paths) {
  const out = [];
  for (const raw of paths || []) {
    if (!raw) continue;
    const p = assertExcelPath(raw);
    approvePath(p);
    out.push(p);
  }
  return out;
}

function assertRpcMethod(method) {
  const m = String(method || '');
  if (!ALLOWED_RPC.has(m)) {
    throw new Error(`Метод запрещён: ${m}`);
  }
  return m;
}

/**
 * Validate / rewrite params for path-sensitive RPCs.
 * @returns {Record<string, unknown>}
 */
function gateRpcParams(method, params) {
  const p = params && typeof params === 'object' ? { ...params } : {};
  if (LOAD_METHODS.has(method)) {
    const filePath = assertApprovedPath(p.path, 'load');
    assertExcelPath(filePath);
    p.path = filePath;
  } else if (EXPORT_METHODS.has(method)) {
    const filePath = assertApprovedPath(p.path, 'export');
    assertExportPath(filePath);
    p.path = filePath;
  }
  return p;
}

function assertSafeExternalUrl(url) {
  let u;
  try {
    u = new URL(String(url));
  } catch {
    throw new Error('Некорректный URL');
  }
  if (u.protocol !== 'https:') {
    throw new Error('Разрешён только https');
  }
  const host = u.hostname.toLowerCase();
  const allowed =
    host === 'github.com' ||
    host === 'www.github.com' ||
    host === 'api.github.com' ||
    host.endsWith('.github.com') ||
    host.endsWith('.githubusercontent.com');
  if (!allowed) {
    throw new Error('Разрешены только ссылки GitHub');
  }
  return u.toString();
}

function assertApprovedOpenPath(filePath) {
  const p = assertApprovedPath(filePath, 'export');
  // open after save: file should exist
  if (!fs.existsSync(p)) {
    throw new Error(`Файл не найден: ${p}`);
  }
  return p;
}

module.exports = {
  ALLOWED_RPC,
  approvePath,
  approvePaths,
  approveLoadPaths,
  isApproved,
  assertRpcMethod,
  gateRpcParams,
  assertSafeExternalUrl,
  assertApprovedOpenPath,
  normalizePath,
};
