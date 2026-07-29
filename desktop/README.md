# Electron UI (Анализ историй)

Веб-интерфейс на **Electron + Vite + React** с Python sidecar (как в «План операций»).

## Запуск (dev)

```bash
# корень репозитория
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

cd desktop
npm install
npm run dev
```

## Возможности UI

- ЭМК / КСГ: загрузка, KPI, таблицы, графики
- Экспорт Excel / TXT
- Настройки порогов КСГ / КСЛП
- Сравнение месяцев КСГ
- Светлая / тёмная тема Slice

## Сборка Windows

```bash
# 1) Python backend (PyInstaller) → desktop/backend/
npm run backend          # macOS/Linux
# npm run backend:win    # Windows (PowerShell)

# 2) Electron unpack
npm run dist:win
# → desktop/release/win-unpacked/
```

Либо одной командой: `npm run dist:all`.

Релизный zip на GitHub собирается CI из `win-unpacked` (Electron + sidecar), не из Tkinter.

## Архитектура

| Слой | Путь |
|------|------|
| Renderer | `desktop/src/` |
| Main / preload | `desktop/electron/` (`window.analiz`) |
| Bridge | `bridge/` JSON-RPC → `lor_analysis` / `ksg_analysis` / `export_reports` |

Tkinter (`main.py`) — **legacy**, только запасной UI. Основной интерфейс — этот Electron-проект.
