'use strict';

const { Menu, app, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');

/** @typedef {{ recent_emk?: string[], recent_ksg?: string[], recent_ops?: string[], date_format?: string }} MenuState */

const DEFAULT_STATE = {
  recent_emk: [],
  recent_ksg: [],
  recent_ops: [],
  date_format: 'dayfirst',
};

/** @type {import('electron').BrowserWindow | null} */
let boundWindow = null;
/** @type {string} */
let projectRoot = '';
/** @type {MenuState} */
let menuState = { ...DEFAULT_STATE };

function sendAction(action, payload) {
  if (boundWindow && !boundWindow.isDestroyed()) {
    boundWindow.webContents.send('menu:action', { action, payload });
  }
}

function existingPaths(paths) {
  return (paths || []).filter((p) => {
    try {
      return p && fs.existsSync(p);
    } catch {
      return false;
    }
  });
}

function recentSubmenu(paths, kind) {
  const items = existingPaths(paths);
  if (!items.length) {
    return [{ label: '(пусто)', enabled: false }];
  }
  return items.map((filePath) => ({
    label: path.basename(filePath),
    click: () => sendAction('open-recent', { kind, path: filePath }),
  }));
}

function openLogFile() {
  const logPath = path.join(projectRoot, 'errors.log');
  if (fs.existsSync(logPath)) {
    void shell.openPath(logPath);
    return;
  }
  sendAction('log-missing');
}

function buildTemplate() {
  const isMac = process.platform === 'darwin';
  const mod = isMac ? 'Cmd' : 'Ctrl';
  const df = menuState.date_format === 'monthfirst' ? 'monthfirst' : 'dayfirst';

  const fileSubmenu = [
    {
      label: 'Открыть…',
      accelerator: `${mod}+O`,
      click: () => sendAction('open'),
    },
    {
      label: 'Сохранить отчёт…',
      accelerator: `${mod}+S`,
      click: () => sendAction('save'),
    },
    { type: 'separator' },
    {
      label: 'Недавние ЭМК',
      submenu: recentSubmenu(menuState.recent_emk, 'emk'),
    },
    {
      label: 'Недавние КСГ',
      submenu: recentSubmenu(menuState.recent_ksg, 'ksg'),
    },
    {
      label: 'Недавние операции',
      submenu: recentSubmenu(menuState.recent_ops, 'ops'),
    },
    { type: 'separator' },
    { label: 'Открыть лог ошибок', click: openLogFile },
    { label: 'Проверить обновления', click: () => sendAction('check-updates') },
  ];

  if (!isMac) {
    fileSubmenu.push({ type: 'separator' });
    fileSubmenu.push({ label: 'Выход', accelerator: `${mod}+Q`, role: 'quit' });
  }

  const editSubmenu = [
    {
      label: 'Копировать выделенное',
      accelerator: `${mod}+C`,
      click: () => sendAction('copy-selection'),
    },
    {
      label: 'Копировать сводку',
      accelerator: `${mod}+Shift+C`,
      click: () => sendAction('copy-summary'),
    },
  ];

  if (!isMac) {
    editSubmenu.push(
      { type: 'separator' },
      { label: 'Вырезать', role: 'cut' },
      { label: 'Вставить', role: 'paste' },
      { label: 'Выделить всё', role: 'selectAll' },
    );
  }

  const settingsSubmenu = [
    { label: 'Все настройки…', click: () => sendAction('settings') },
    { label: 'Переключить тему', click: () => sendAction('toggle-theme') },
    { type: 'separator' },
    {
      label: 'Дата: ДД.ММ.ГГГГ',
      type: 'radio',
      checked: df === 'dayfirst',
      click: () => sendAction('date-format', { value: 'dayfirst' }),
    },
    {
      label: 'Дата: ММ.ДД.ГГГГ',
      type: 'radio',
      checked: df === 'monthfirst',
      click: () => sendAction('date-format', { value: 'monthfirst' }),
    },
  ];

  const helpSubmenu = [
    { label: 'Что нового…', click: () => sendAction('whats-new') },
    { label: 'О программе', click: () => sendAction('about') },
  ];

  /** @type {Electron.MenuItemConstructorOptions[]} */
  const template = [];

  if (isMac) {
    template.push({
      label: app.name,
      submenu: [
        { label: 'О программе', click: () => sendAction('about') },
        { type: 'separator' },
        {
          label: 'Настройки…',
          accelerator: 'Cmd+,',
          click: () => sendAction('settings'),
        },
        { type: 'separator' },
        { role: 'services', label: 'Службы' },
        { type: 'separator' },
        { role: 'hide', label: 'Скрыть' },
        { role: 'hideOthers', label: 'Скрыть остальные' },
        { role: 'unhide', label: 'Показать все' },
        { type: 'separator' },
        { role: 'quit', label: 'Выход' },
      ],
    });
  }

  template.push(
    { label: 'Файл', submenu: fileSubmenu },
    { label: 'Правка', submenu: editSubmenu },
    { label: 'Настройки', submenu: settingsSubmenu },
    { label: 'Справка', submenu: helpSubmenu },
  );

  if (isMac) {
    template.push({
      label: 'Окно',
      submenu: [
        { role: 'minimize', label: 'Свернуть' },
        { role: 'zoom', label: 'Масштаб' },
        { type: 'separator' },
        { role: 'front', label: 'На передний план' },
      ],
    });
  }

  return template;
}

function rebuildApplicationMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate(buildTemplate()));
}

function bindApplicationMenu(mainWindow, rootDir) {
  boundWindow = mainWindow;
  projectRoot = rootDir || '';
  rebuildApplicationMenu();
}

function syncMenuState(state) {
  menuState = {
    recent_emk: Array.isArray(state?.recent_emk) ? state.recent_emk : [],
    recent_ksg: Array.isArray(state?.recent_ksg) ? state.recent_ksg : [],
    recent_ops: Array.isArray(state?.recent_ops) ? state.recent_ops : [],
    date_format: state?.date_format === 'monthfirst' ? 'monthfirst' : 'dayfirst',
  };
  rebuildApplicationMenu();
}

module.exports = {
  bindApplicationMenu,
  syncMenuState,
  rebuildApplicationMenu,
};
