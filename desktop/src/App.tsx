import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import { BarChart } from './components/BarChart';
import { DataTable } from './components/DataTable';
import { ExportDialog } from './components/ExportDialog';
import { SettingsDialog, type AppConfig } from './components/SettingsDialog';
import {
  DEFAULT_COMPARE_CHARTS,
  KsgComparePanel,
  type CompareChartsState,
  type CompareResult,
} from './components/KsgComparePanel';
import type { OpItem } from './components/SearchableSelect';
import {
  ViolationsSummaryDialog,
  type ViolationSection,
} from './components/ViolationsSummaryDialog';
import { copyText } from './lib/clipboard';
import './App.css';

type Theme = 'dark' | 'light';
type MainTab = 'emk' | 'ksg';

type EmkAnalysis = {
  department: string;
  file_name?: string;
  report_basename?: string;
  period_start?: string | null;
  period_end?: string | null;
  total_patients: number;
  avg_beddays: number;
  urgent: number;
  planned: number;
  skp_count: number;
  skp_days_0: number;
  skp_days_1: number;
  violation_share: Record<string, unknown>[];
  violations: Record<string, unknown>[];
  doctor_stats: Record<string, unknown>[];
  ids_stats: Record<string, unknown>[];
  long_stay: Record<string, unknown>[];
  skp_cases: Record<string, unknown>[];
  skp_operations: Record<string, unknown>[];
  violations_total: number;
  cases_with_violations?: number;
  cases_without_violations?: number;
  age_dist?: Record<string, number>;
  long_stay_days?: number;
  violations_summary?: ViolationSection[];
};

type KsgFile = {
  name: string;
  path: string;
  label?: string;
  total_patients?: number;
  total_sum?: number;
  avg_kz_total?: number;
};

type KsgAnalysis = {
  total_patients?: number;
  total_sum?: number;
  avg_kz_total?: number;
  patient_counts?: Record<string, unknown>[] | Record<string, number>;
  sum_by_doctor?: Record<string, unknown>[];
  ops_pivot?: Record<string, unknown>[];
  unknown_codes?: string[];
  low_money?: Record<string, unknown>[];
  high_money?: Record<string, unknown>[];
  no_service?: Record<string, unknown>[];
  kslp_issues?: Record<string, unknown>[];
  age_dist?: Record<string, number>;
};

const VIOLATION_COLORS: Record<string, string> = {
  'Первичный осмотр': '#3d9cf0',
  Эпикриз: '#9B7ED9',
  МКСБ: '#e85d5d',
  'Лекарственные назначения': '#3ecf8e',
  'Дневниковые записи': '#e6a23c',
  ИДС: '#E67E22',
  'Длительная госпитализация': '#8b95a8',
  'Протоколы операций': '#c62828',
};

function api() {
  if (!window.analiz) throw new Error('Electron bridge недоступен (window.analiz)');
  return window.analiz;
}

async function rpc<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  return (await api().rpc(method, params)) as T;
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

function fmtDateRu(iso: string | null | undefined): string {
  if (!iso) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (m) return `${m[3]}.${m[2]}.${m[1]}`;
  try {
    return new Date(iso).toLocaleDateString('ru-RU');
  } catch {
    return iso;
  }
}

function fmtNum(value: unknown, digits = 0): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('ru-RU', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-title">{title}</div>
      <div className="kpi-value">{value}</div>
    </div>
  );
}

export default function App() {
  const [version, setVersion] = useState('?.?.?');
  const [theme, setTheme] = useState<Theme>('dark');
  const [tab, setTab] = useState<MainTab>('emk');
  const [bridgeOk, setBridgeOk] = useState(false);
  const [status, setStatus] = useState('Запуск…');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<AppConfig>({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [violOpen, setViolOpen] = useState(false);
  const [operations, setOperations] = useState<OpItem[]>([]);
  const [deptOptions, setDeptOptions] = useState<string[]>([]);

  const [departments, setDepartments] = useState<string[]>([]);
  const [department, setDepartment] = useState('');
  const [emkFile, setEmkFile] = useState<string | null>(null);
  const [emk, setEmk] = useState<EmkAnalysis | null>(null);
  const [emkSub, setEmkSub] = useState<'share' | 'violations' | 'doctors' | 'skp' | 'age'>('share');

  const [ksgFiles, setKsgFiles] = useState<KsgFile[]>([]);
  const [ksgActive, setKsgActive] = useState(0);
  const [ksg, setKsg] = useState<KsgAnalysis | null>(null);
  const [ksgRef, setKsgRef] = useState('');
  const [ksgSub, setKsgSub] = useState<'doctors' | 'cases' | 'ops' | 'compare'>('doctors');
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [compareIndices, setCompareIndices] = useState<number[]>([]);
  const [compareCharts, setCompareCharts] = useState<CompareChartsState>(DEFAULT_COMPARE_CHARTS);
  const [dragOver, setDragOver] = useState(false);
  const [copyFlash, setCopyFlash] = useState(false);
  const prefsReady = useRef(false);
  const persistTimer = useRef<number | null>(null);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    setCompareIndices(ksgFiles.map((_, i) => i));
  }, [ksgFiles]);

  useEffect(() => {
    if (!prefsReady.current) return;
    if (persistTimer.current) window.clearTimeout(persistTimer.current);
    persistTimer.current = window.setTimeout(() => {
      void (async () => {
        try {
          const res = await rpc<{ config: AppConfig }>('config.set', {
            config: {
              last_main_tab: tab === 'ksg' ? 1 : 0,
              ui_prefs: {
                main_tab: tab,
                emk_sub: emkSub,
                ksg_sub: ksgSub,
                compare_charts: compareCharts,
              },
            },
          });
          setConfig(res.config);
        } catch {
          // ignore persist errors
        }
      })();
    }, 400);
    return () => {
      if (persistTimer.current) window.clearTimeout(persistTimer.current);
    };
  }, [tab, emkSub, ksgSub, compareCharts]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await api().getBridgeStatus();
        if (cancelled) return;
        setBridgeOk(!!st.ok);
        setStatus(st.ok ? 'Готово' : st.detail || 'Мост недоступен');
        const ver = await api().getAppVersion();
        if (!cancelled) setVersion(ver);
        const cfgRes = await rpc<{ config: AppConfig }>('config.get');
        if (cancelled) return;
        setConfig(cfgRes.config || {});
        const t = cfgRes.config?.theme;
        if (t === 'slice-light' || t === 'light') setTheme('light');
        else setTheme('dark');
        const prefs = cfgRes.config?.ui_prefs;
        if (prefs?.main_tab === 'ksg' || prefs?.main_tab === 'emk') {
          setTab(prefs.main_tab);
        } else if (cfgRes.config?.last_main_tab === 1) {
          setTab('ksg');
        }
        const emkSubs = ['share', 'violations', 'doctors', 'skp', 'age'] as const;
        if (prefs?.emk_sub && (emkSubs as readonly string[]).includes(prefs.emk_sub)) {
          setEmkSub(prefs.emk_sub as typeof emkSubs[number]);
        }
        const ksgSubs = ['doctors', 'cases', 'ops', 'compare'] as const;
        if (prefs?.ksg_sub && (ksgSubs as readonly string[]).includes(prefs.ksg_sub)) {
          setKsgSub(prefs.ksg_sub as typeof ksgSubs[number]);
        }
        if (prefs?.compare_charts) {
          setCompareCharts({ ...DEFAULT_COMPARE_CHARTS, ...prefs.compare_charts });
        }
        prefsReady.current = true;
        try {
          const ops = await rpc<{ items: OpItem[] }>('ref.operations');
          if (!cancelled) setOperations(ops.items || []);
        } catch {
          // optional
        }
        try {
          const deps = await rpc<{ departments: string[] }>('ref.departments');
          if (!cancelled) setDeptOptions(deps.departments || []);
        } catch {
          // optional
        }
      } catch (e) {
        if (!cancelled) {
          setBridgeOk(false);
          setStatus(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleTheme = useCallback(async () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try {
      const res = await rpc<{ config: AppConfig }>('config.set', {
        config: { theme: next === 'dark' ? 'slice-dark' : 'slice-light' },
      });
      setConfig(res.config);
    } catch {
      // local only
    }
  }, [theme]);

  const loadEmkFromPath = useCallback(async (path: string) => {
    setError(null);
    setBusy(true);
    try {
      setStatus('Загрузка ЭМК…');
      const loaded = await rpc<{
        file_name: string;
        departments: string[];
        preferred_department: string;
        known_departments?: string[];
      }>('emk.load', { path });
      setEmkFile(loaded.file_name);
      setDepartments(loaded.departments);
      if (loaded.known_departments?.length) setDeptOptions(loaded.known_departments);
      else setDeptOptions(loaded.departments);
      const dept = loaded.preferred_department || loaded.departments[0] || '';
      setDepartment(dept);
      setStatus('Анализ ЭМК…');
      const analysis = await rpc<EmkAnalysis>('emk.analyze', { department: dept });
      setEmk(analysis);
      setTab('emk');
      setStatus(`ЭМК: ${loaded.file_name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus('Ошибка загрузки ЭМК');
    } finally {
      setBusy(false);
    }
  }, []);

  const loadEmk = useCallback(async () => {
    const path = await api().openExcelDialog({ title: 'Файл ЭМК' });
    if (!path || Array.isArray(path)) return;
    await loadEmkFromPath(path);
  }, [loadEmkFromPath]);

  const reanalyzeEmk = useCallback(
    async (dept: string) => {
      setDepartment(dept);
      if (!emkFile) return;
      setBusy(true);
      setError(null);
      try {
        setStatus('Анализ ЭМК…');
        const analysis = await rpc<EmkAnalysis>('emk.analyze', { department: dept });
        setEmk(analysis);
        setStatus(`ЭМК: ${analysis.file_name || emkFile}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [emkFile],
  );

  const loadKsgFromPaths = useCallback(async (list: string[]) => {
    if (!list.length) return;
    setError(null);
    setBusy(true);
    try {
      let lastAnalysis: KsgAnalysis | null = null;
      let files: KsgFile[] = [];
      let active = 0;
      let ref = '';
      for (const path of list) {
        setStatus(`Загрузка КСГ: ${path.split(/[/\\]/).pop()}`);
        const res = await rpc<{
          files: KsgFile[];
          active: number;
          reference_status: string;
          analysis: KsgAnalysis;
        }>('ksg.load', { path });
        files = res.files;
        active = res.active;
        ref = res.reference_status;
        lastAnalysis = res.analysis;
      }
      setKsgFiles(files);
      setKsgActive(active);
      setKsgRef(ref);
      setKsg(lastAnalysis);
      setCompare(null);
      setTab('ksg');
      setStatus(`КСГ: ${files.length} файл(ов)`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus('Ошибка загрузки КСГ');
    } finally {
      setBusy(false);
    }
  }, []);

  const loadKsg = useCallback(async () => {
    const paths = await api().openExcelDialog({
      title: 'Файлы КСГ',
      multiSelections: true,
    });
    const list = Array.isArray(paths) ? paths : paths ? [paths] : [];
    await loadKsgFromPaths(list);
  }, [loadKsgFromPaths]);

  const selectKsg = useCallback(async (index: number) => {
    setBusy(true);
    setError(null);
    try {
      const res = await rpc<{ active: number; analysis: KsgAnalysis }>('ksg.setActive', { index });
      setKsgActive(res.active);
      setKsg(res.analysis);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const removeKsg = useCallback(async () => {
    if (!ksgFiles.length) return;
    setBusy(true);
    try {
      const res = await rpc<{
        files: KsgFile[];
        active: number;
        reference_status: string;
      }>('ksg.remove', { index: ksgActive });
      setKsgFiles(res.files);
      setKsgActive(res.active);
      setKsgRef(res.reference_status);
      setCompare(null);
      if (res.files.length) {
        const active = await rpc<{ analysis: KsgAnalysis }>('ksg.setActive', { index: res.active });
        setKsg(active.analysis);
      } else {
        setKsg(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [ksgActive, ksgFiles.length]);

  const reanalyzeKsg = useCallback(async () => {
    if (!ksgFiles.length) return;
    setBusy(true);
    setError(null);
    try {
      setStatus('Пересчёт КСГ…');
      const res = await rpc<{
        files: KsgFile[];
        active: number;
        reference_status: string;
        analysis: KsgAnalysis | null;
      }>('ksg.reanalyze', {});
      setKsgFiles(res.files);
      setKsgActive(res.active);
      setKsgRef(res.reference_status);
      setKsg(res.analysis);
      setCompare(null);
      setStatus('КСГ пересчитан');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [ksgFiles.length]);

  const runCompare = useCallback(async () => {
    const indices = compareIndices.length
      ? compareIndices
      : ksgFiles.map((_, i) => i);
    if (indices.length < 2) {
      setError('Для сравнения выберите минимум 2 файла КСГ');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await rpc<CompareResult>('ksg.compare', { indices });
      setCompare(res);
      setKsgSub('compare');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [compareIndices, ksgFiles]);

  const copySummary = useCallback(async () => {
    const lines: string[] = [];
    if (tab === 'emk' && emk) {
      lines.push('Сводка ЭМК');
      lines.push(`Файл: ${emk.file_name || emkFile || '—'}`);
      lines.push(`Отделение: ${emk.department || department || '—'}`);
      lines.push(`Пациенты: ${fmtNum(emk.total_patients)}`);
      lines.push(`Ср. койко-дни: ${fmtNum(emk.avg_beddays, 1)}`);
      lines.push(`Экстренные: ${fmtNum(emk.urgent)}`);
      lines.push(`Плановые: ${fmtNum(emk.planned)}`);
      lines.push(`Нарушения: ${fmtNum(emk.violations_total)}`);
      lines.push(`СКП: ${fmtNum(emk.skp_count)}`);
    } else if (tab === 'ksg' && ksg) {
      lines.push('Сводка КСГ');
      lines.push(`Файл: ${ksgFiles[ksgActive]?.label || ksgFiles[ksgActive]?.name || '—'}`);
      lines.push(`Пациенты: ${fmtNum(ksg.total_patients)}`);
      lines.push(`Сумма: ${fmtNum(ksg.total_sum, 0)}`);
      lines.push(`Средний КЗ: ${fmtNum(ksg.avg_kz_total, 3)}`);
      lines.push(`Без услуги: ${fmtNum(ksg.no_service?.length)}`);
      lines.push(`КСЛП: ${fmtNum(ksg.kslp_issues?.length)}`);
    } else {
      setError('Нет данных для копирования сводки');
      return;
    }
    try {
      await copyText(lines.join('\n'));
      setCopyFlash(true);
      window.setTimeout(() => setCopyFlash(false), 1500);
      setStatus('Сводка скопирована');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [tab, emk, emkFile, department, ksg, ksgFiles, ksgActive]);

  const onDropFiles = useCallback(
    async (e: DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files || []);
      if (!files.length) return;
      const getPath = api().getPathForFile;
      if (!getPath) {
        setError('Drag-and-drop недоступен в этой среде');
        return;
      }
      const paths = files
        .map((f) => getPath(f))
        .filter((p): p is string => !!p && /\.(xlsx|xls|xlsm)$/i.test(p));
      if (!paths.length) {
        setError('Перетащите Excel-файлы (.xlsx / .xls)');
        return;
      }
      if (tab === 'ksg' || paths.length > 1) {
        await loadKsgFromPaths(paths);
      } else {
        await loadEmkFromPath(paths[0]);
      }
    },
    [tab, loadEmkFromPath, loadKsgFromPaths],
  );

  const doExport = useCallback(
    async (opts: { format: 'xlsx' | 'txt'; sections?: Record<string, boolean> }) => {
      const isEmk = tab === 'emk';
      const defaultName = isEmk
        ? `${emk?.report_basename || 'Отчет ЭМК'}.${opts.format}`
        : `Отчет_КСГ_${ksgFiles[ksgActive]?.label || 'файл'}.${opts.format}`;
      const path =
        opts.format === 'xlsx'
          ? await api().saveExcelDialog({ defaultPath: defaultName })
          : await api().saveTextDialog({ defaultPath: defaultName });
      if (!path) return;
      setStatus('Сохранение…');
      const res = await rpc<{ path: string }>(isEmk ? 'emk.export' : 'ksg.export', {
        path,
        format: opts.format,
        sections: opts.sections,
        index: ksgActive,
      });
      setStatus(`Сохранено: ${res.path}`);
      await api().openPath(res.path);
    },
    [tab, emk, ksgFiles, ksgActive],
  );

  const emkShow = useCallback(
    (key: string) => config.emk_display?.[key] !== false,
    [config.emk_display],
  );
  const ksgShow = useCallback(
    (key: string) => config.ksg_display?.[key] !== false,
    [config.ksg_display],
  );

  const shareBars = useMemo(() => {
    if (!emk?.violation_share?.length) return [];
    return emk.violation_share.map((row) => {
      const label = String(row['Тип нарушения'] ?? '');
      return {
        label,
        value: Number(row['Доля, %'] ?? 0),
        color: VIOLATION_COLORS[label],
      };
    });
  }, [emk]);

  const coverageBars = useMemo(() => {
    if (!emk) return [];
    return [
      {
        label: 'С нарушениями',
        value: Number(emk.cases_with_violations ?? 0),
        color: 'var(--danger)',
      },
      {
        label: 'Без нарушений',
        value: Number(emk.cases_without_violations ?? 0),
        color: 'var(--ok)',
      },
    ];
  }, [emk]);

  const ageBars = useMemo(() => {
    if (!emk?.age_dist) return [];
    return Object.entries(emk.age_dist).map(([label, value]) => ({
      label,
      value: Number(value) || 0,
    }));
  }, [emk]);

  return (
    <div
      className={`shell${dragOver ? ' shell--drag' : ''}`}
      onDragEnter={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragOver(false);
      }}
      onDrop={(e) => void onDropFiles(e)}
    >
      {dragOver && (
        <div className="drop-overlay" aria-hidden>
          Отпустите Excel-файл для загрузки
          <span className="muted">Один файл → ЭМК (если открыта вкладка ЭМК); несколько → КСГ</span>
        </div>
      )}
      <header className="topbar">
        <div className="brand">
          <div className="brand-title">Анализ работы отделения</div>
          <div className="brand-meta">v{version} · Electron</div>
        </div>
        <div className="topbar-actions">
          <button className="btn btn-ghost" type="button" onClick={() => setSettingsOpen(true)}>
            Настройки
          </button>
          <button className="btn btn-ghost" type="button" onClick={toggleTheme}>
            {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={`tab ${tab === 'emk' ? 'active' : ''}`}
          onClick={() => setTab('emk')}
        >
          Анализ ЭМК
        </button>
        <button
          type="button"
          className={`tab ${tab === 'ksg' ? 'active' : ''}`}
          onClick={() => setTab('ksg')}
        >
          Анализ КСГ
        </button>
      </nav>

      <main className="workspace">
        {error && <div className="error-banner">{error}</div>}

        {tab === 'emk' && (
          <>
            <div className="toolbar">
              <button className="btn btn-primary" type="button" disabled={busy} onClick={loadEmk}>
                Загрузить Excel
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !emk}
                onClick={() => setExportOpen(true)}
              >
                Сохранить…
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !emk}
                onClick={() => void copySummary()}
              >
                {copyFlash && tab === 'emk' ? 'Скопировано' : 'Копировать сводку'}
              </button>
              <button
                className="btn btn-accent"
                type="button"
                disabled={busy || !emk || !(emk.violations_total > 0)}
                onClick={() => setViolOpen(true)}
              >
                Сводка нарушений
              </button>
              {departments.length > 0 && (
                <label className="field">
                  Отделение
                  <select
                    value={department}
                    disabled={busy}
                    onChange={(e) => void reanalyzeEmk(e.target.value)}
                  >
                    {departments.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>

            {!emk ? (
              <div className="empty">
                <h2>Анализ ЭМК</h2>
                <p>Загрузите Excel-отчёт по заполнению историй болезни или перетащите файл сюда.</p>
              </div>
            ) : (
              <>
                <div className="context-bar">
                  <span>
                    Файл: <strong>{emk.file_name || emkFile || '—'}</strong>
                  </span>
                  <span>
                    Период:{' '}
                    <strong>
                      {emk.period_start || emk.period_end
                        ? `${fmtDateRu(emk.period_start)} — ${fmtDateRu(emk.period_end)}`
                        : 'не определён'}
                    </strong>
                  </span>
                  {emk.department && (
                    <span>
                      Отделение: <strong>{emk.department}</strong>
                    </span>
                  )}
                </div>
                <div className="kpi-grid">
                  {emkShow('kpi_patients') && (
                    <Kpi title="Пациенты" value={fmtNum(emk.total_patients)} />
                  )}
                  {emkShow('kpi_avg_beddays') && (
                    <Kpi title="Ср. койко-дни" value={fmtNum(emk.avg_beddays, 1)} />
                  )}
                  {emkShow('kpi_urgent') && (
                    <Kpi title="Экстренные" value={fmtNum(emk.urgent)} />
                  )}
                  {emkShow('kpi_planned') && (
                    <Kpi title="Плановые" value={fmtNum(emk.planned)} />
                  )}
                  {emkShow('kpi_violations') && (
                    <Kpi title="Нарушения" value={fmtNum(emk.violations_total)} />
                  )}
                  {emkShow('kpi_skp') && <Kpi title="СКП" value={fmtNum(emk.skp_count)} />}
                </div>

                <div className="subtabs">
                  {(
                    [
                      ['share', 'Структура', 'section_share'],
                      ['age', 'Возраст', 'section_age'],
                      ['violations', 'Нарушения', 'section_violations'],
                      ['doctors', 'Врачи', 'section_doctors'],
                      ['skp', 'СКП', 'section_skp'],
                    ] as const
                  )
                    .filter(([, , key]) => emkShow(key))
                    .map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${emkSub === id ? 'active' : ''}`}
                      onClick={() => setEmkSub(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div className="panel">
                  {emkSub === 'share' && (
                    <>
                      <div className="charts-row">
                        <div className="chart-block">
                          <h4>Структура нарушений, %</h4>
                          <BarChart items={shareBars} unit="%" />
                        </div>
                        <div className="chart-block chart-block--split">
                          <h4>Истории с / без нарушений</h4>
                          <BarChart items={coverageBars} />
                        </div>
                      </div>
                      <DataTable rows={emk.violation_share} />
                    </>
                  )}
                  {emkSub === 'age' && (
                    <>
                      <BarChart items={ageBars} />
                      <div style={{ marginTop: 12 }}>
                        <DataTable
                          rows={Object.entries(emk.age_dist || {}).map(([k, v]) => ({
                            'Возрастная группа': k,
                            Количество: v,
                          }))}
                        />
                      </div>
                    </>
                  )}
                  {emkSub === 'violations' && <DataTable rows={emk.violations} />}
                  {emkSub === 'doctors' && (
                    <>
                      <h3>Сводка по врачам</h3>
                      <DataTable rows={emk.doctor_stats} />
                      <h3 style={{ marginTop: 16 }}>ИДС</h3>
                      <DataTable rows={emk.ids_stats} />
                    </>
                  )}
                  {emkSub === 'skp' && (
                    <>
                      <p className="muted" style={{ marginTop: 0 }}>
                        0 койко-дней: {emk.skp_days_0} · 1 койко-день: {emk.skp_days_1}
                      </p>
                      <h3>Истории СКП</h3>
                      <DataTable rows={emk.skp_cases} />
                      <h3 style={{ marginTop: 16 }}>Операции / услуги</h3>
                      <DataTable rows={emk.skp_operations} />
                    </>
                  )}
                </div>
              </>
            )}
          </>
        )}

        {tab === 'ksg' && (
          <>
            <div className="toolbar">
              <button className="btn btn-primary" type="button" disabled={busy} onClick={loadKsg}>
                Загрузить КСГ
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksgFiles.length}
                onClick={() => void removeKsg()}
              >
                Удалить
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksgFiles.length}
                onClick={() => void reanalyzeKsg()}
              >
                Пересчитать
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || compareIndices.length < 2}
                onClick={() => void runCompare()}
              >
                Сравнить месяцы
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksg}
                onClick={() => setExportOpen(true)}
              >
                Сохранить…
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksg}
                onClick={() => void copySummary()}
              >
                {copyFlash && tab === 'ksg' ? 'Скопировано' : 'Копировать сводку'}
              </button>
              {ksgRef && <span className="muted">{ksgRef}</span>}
            </div>

            {ksgFiles.length > 0 && (
              <div className="subtabs">
                {ksgFiles.map((f, i) => (
                  <button
                    key={f.path}
                    type="button"
                    className={`chip ${ksgActive === i ? 'active' : ''}`}
                    disabled={busy}
                    onClick={() => void selectKsg(i)}
                  >
                    {f.label || f.name}
                  </button>
                ))}
              </div>
            )}

            {ksgFiles.length >= 2 && (
              <div className="compare-pick">
                <span className="muted">Сравнивать:</span>
                {ksgFiles.map((f, i) => {
                  const on = compareIndices.includes(i);
                  return (
                    <label key={f.path} className="compare-pick__item">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={busy}
                        onChange={() => {
                          setCompareIndices((prev) => {
                            if (prev.includes(i)) return prev.filter((x) => x !== i);
                            return [...prev, i].sort((a, b) => a - b);
                          });
                          setCompare(null);
                        }}
                      />
                      {f.label || f.name}
                    </label>
                  );
                })}
              </div>
            )}

            {!ksg ? (
              <div className="empty">
                <h2>Анализ КСГ</h2>
                <p>Загрузите один или несколько месячных отчётов КСГ или перетащите файлы сюда.</p>
              </div>
            ) : (
              <>
                <div className="kpi-grid">
                  {ksgShow('kpi_patients') && (
                    <Kpi title="Пациенты" value={fmtNum(ksg.total_patients)} />
                  )}
                  {ksgShow('kpi_sum') && (
                    <Kpi title="Сумма, ₽" value={fmtNum(ksg.total_sum, 0)} />
                  )}
                  {ksgShow('kpi_kz') && (
                    <Kpi title="Средний КЗ" value={fmtNum(ksg.avg_kz_total, 3)} />
                  )}
                  {ksgShow('kpi_no_service') && (
                    <Kpi title="Без услуги" value={fmtNum(ksg.no_service?.length)} />
                  )}
                  {ksgShow('kpi_kslp') && (
                    <Kpi title="КСЛП" value={fmtNum(ksg.kslp_issues?.length)} />
                  )}
                </div>

                <div className="subtabs">
                  {(
                    [
                      ['doctors', 'Суммы по врачам', 'section_doctors'],
                      ['cases', 'Случаи', 'section_cases'],
                      ['ops', 'Операции', 'section_ops'],
                      ['compare', 'Сравнение', 'section_compare'],
                    ] as const
                  )
                    .filter(([, , key]) => ksgShow(key))
                    .map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${ksgSub === id ? 'active' : ''}`}
                      onClick={() => setKsgSub(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div className="panel">
                  {ksgSub === 'doctors' && (
                    <>
                      <BarChart
                        items={(ksg.sum_by_doctor || []).map((row) => ({
                          label: String(row['Врач'] ?? ''),
                          value: Number(row['Сумма'] ?? row['Сумма к оплате'] ?? 0),
                        }))}
                      />
                      <div style={{ marginTop: 12 }}>
                        <DataTable rows={ksg.sum_by_doctor || []} />
                      </div>
                    </>
                  )}
                  {ksgSub === 'cases' && (
                    <>
                      <h3>Дешёвые случаи</h3>
                      <DataTable rows={ksg.low_money || []} />
                      <h3 style={{ marginTop: 16 }}>Дорогие случаи</h3>
                      <DataTable rows={ksg.high_money || []} />
                      <h3 style={{ marginTop: 16 }}>КСЛП</h3>
                      <DataTable rows={ksg.kslp_issues || []} />
                    </>
                  )}
                  {ksgSub === 'ops' && (
                    <>
                      <DataTable rows={ksg.ops_pivot || []} />
                      {!!ksg.unknown_codes?.length && (
                        <p className="muted" style={{ marginTop: 12 }}>
                          Нераспознанные коды: {ksg.unknown_codes.slice(0, 30).join(', ')}
                          {ksg.unknown_codes.length > 30 ? '…' : ''}
                        </p>
                      )}
                    </>
                  )}
                  {ksgSub === 'compare' &&
                    (compare ? (
                      <KsgComparePanel
                        compare={compare}
                        chartsOn={compareCharts}
                        onChartsChange={setCompareCharts}
                      />
                    ) : (
                      <div className="muted">
                        Отметьте месяцы выше и нажмите «Сравнить месяцы» (нужно ≥ 2).
                      </div>
                    ))}
                </div>
              </>
            )}
          </>
        )}
      </main>

      <footer className="status-line">
        <span className={`dot ${bridgeOk ? 'ok' : ''}`} />
        <span>{status}</span>
      </footer>

      {settingsOpen && (
        <SettingsDialog
          initial={config}
          operations={operations}
          departments={deptOptions.length ? deptOptions : departments}
          onClose={() => setSettingsOpen(false)}
          onSave={async (cfg) => {
            const res = await rpc<{ config: AppConfig }>('config.set', { config: cfg });
            setConfig(res.config);
            if (res.config.known_departments?.length) {
              setDeptOptions(res.config.known_departments);
            }
            if (emkFile) await reanalyzeEmk(department);
            if (ksgFiles.length) await reanalyzeKsg();
          }}
        />
      )}

      {violOpen && emk?.violations_summary && (
        <ViolationsSummaryDialog
          sections={emk.violations_summary}
          onClose={() => setViolOpen(false)}
        />
      )}

      {exportOpen && (
        <ExportDialog
          kind={tab === 'emk' ? 'emk' : 'ksg'}
          defaultName={
            tab === 'emk'
              ? emk?.report_basename || 'Отчет ЭМК'
              : `Отчет_КСГ_${ksgFiles[ksgActive]?.label || 'файл'}`
          }
          onClose={() => setExportOpen(false)}
          onExport={doExport}
        />
      )}
    </div>
  );
}
