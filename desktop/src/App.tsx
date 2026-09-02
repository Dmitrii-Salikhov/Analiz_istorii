import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import { BarChart, type BarGroup, type BarItem } from './components/BarChart';
import { DataTable } from './components/DataTable';
import { ExportDialog } from './components/ExportDialog';
import { OpsPrintDialog } from './components/OpsPrintDialog';
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
import {
  ViolationTypeDialog,
  type ViolationTypeRow,
} from './components/ViolationTypeDialog';
import { copyText, copySelectionFromDocument, formatShortPersonName, opsRowsToCompactCopy } from './lib/clipboard';
import { fmtNum } from './lib/format';
import {
  KSG_CASE_COLUMN_ORDER,
  normalizeKsgCaseRows,
} from './lib/ksgCaseTables';
import { Modal } from './components/Modal';
import {
  EmkDepartmentScope,
  type EmkScopeMode,
  type EmkSummaryMode,
} from './components/EmkDepartmentScope';
import './App.css';

type Theme = 'dark' | 'light';
type MainTab = 'emk' | 'ksg' | 'ops';

type OpsIssueRow = {
  КВС?: string;
  Пациент?: string;
  Хирург?: string;
  Услуга?: string;
  Длительность?: string;
  Причина?: string;
  'Опер.стол'?: string;
  Отделение?: string;
};

type EmkScope = 'single' | 'multi' | 'all';

type OpsAnalysis = {
  file_name?: string;
  department?: string;
  departments?: string[];
  scope?: EmkScope;
  departments_in_scope?: string[];
  departments_total?: number;
  total_ops: number;
  long_op_hours: number;
  long_count: number;
  missing_table_count: number;
  long_ops: OpsIssueRow[];
  missing_table: OpsIssueRow[];
  violations_summary?: Record<string, unknown>[];
};

type EmkAnalysis = {
  department: string;
  scope?: EmkScope;
  departments_in_scope?: string[];
  departments_total?: number;
  emk_variant?: 'discharged' | 'current';
  emk_variant_label?: string;
  as_of?: string | null;
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
  violation_share_by_snils?: Record<string, unknown>[];
  violations: Record<string, unknown>[];
  doctor_stats: Record<string, unknown>[];
  ids_stats: Record<string, unknown>[];
  long_stay: Record<string, unknown>[];
  skp_cases: Record<string, unknown>[];
  skp_operations: Record<string, unknown>[];
  violations_total: number;
  cases_with_violations?: number;
  cases_without_violations?: number;
  snils_available?: boolean;
  cases_coverage_by_snils?: {
    with_violations_snils: number;
    with_violations_no_snils: number;
    without_violations_snils: number;
    without_violations_no_snils: number;
  } | null;
  cases_coverage_lists?: {
    with_violations?: Record<string, unknown>[];
    without_violations?: Record<string, unknown>[];
    with_violations_snils?: Record<string, unknown>[];
    with_violations_no_snils?: Record<string, unknown>[];
    without_violations_snils?: Record<string, unknown>[];
    without_violations_no_snils?: Record<string, unknown>[];
  };
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
  policy_issues?: Record<string, unknown>[];
  policy_check_enabled?: boolean;
  policy_check_available?: boolean;
  total_policy_issues?: number;
  other_violations?: Record<string, number>;
  by_department?: Record<string, unknown>[];
  age_dist?: Record<string, number>;
  department?: string;
  scope?: EmkScope;
  departments?: string[];
  departments_in_scope?: string[];
  departments_total?: number;
  period?: string;
  period_label?: string;
  periods?: { id: string; label: string }[];
  source?: 'ksg' | 'other';
  has_other_services?: boolean;
};

type ChangelogEntry = {
  version: string;
  title: string;
  items: string[];
};

const VIOLATION_COLORS: Record<string, string> = {
  'Первичный осмотр': '#3d9cf0',
  Эпикриз: '#9B7ED9',
  МКСБ: '#e85d5d',
  'Лекарственные назначения': '#3ecf8e',
  'Дневниковые записи': '#e6a23c',
  'Лабораторные исследования': '#1abc9c',
  'Инструментальные исследования': '#5c6bc0',
  'Консультативные услуги': '#8e6bbf',
  'Реанимационные дневники': '#d35400',
  'ЭМД выписной эпикриз': '#2c7a7b',
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

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function isoFromEmkDate(value: string | null | undefined): string {
  if (!value) return todayIso();
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : todayIso();
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-title">{title}</div>
      <div className="kpi-value">{value}</div>
    </div>
  );
}

type ColumnMapping = {
  matched?: { file: string; canonical: string }[];
  missing?: string[];
  unused_headers?: string[];
};

function activeProfileLabel(cfg: AppConfig, kind: 'emk' | 'ksg' | 'ops'): string {
  const rp = cfg.report_profiles;
  const fallback =
    kind === 'emk' ? 'ЭМК стандарт' : kind === 'ksg' ? 'КСГ стандарт' : 'Операции стандарт';
  if (!rp) return fallback;
  const activeId =
    (kind === 'emk' ? rp.emk_active : kind === 'ksg' ? rp.ksg_active : rp.ops_active) || 'default';
  const bucket = kind === 'emk' ? rp.emk : kind === 'ksg' ? rp.ksg : rp.ops;
  const name = bucket?.[activeId]?.name;
  return name || activeId;
}

function mappingStatusSuffix(
  profileName: string | undefined,
  mapping: ColumnMapping | null | undefined,
): string {
  const matched = mapping?.matched?.length ?? 0;
  const name = profileName || 'профиль';
  return `Профиль: ${name} · сопоставлено ${matched} полей`;
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
  const [opsPrintOpen, setOpsPrintOpen] = useState(false);
  const [violOpen, setViolOpen] = useState(false);
  const [violTypeOpen, setViolTypeOpen] = useState<string | null>(null);
  const [coverageListOpen, setCoverageListOpen] = useState<{
    title: string;
    key: string;
  } | null>(null);
  const [violTableFilter, setViolTableFilter] = useState('');
  const [violTableFilterKey, setViolTableFilterKey] = useState(0);
  const [operations, setOperations] = useState<OpItem[]>([]);
  const [deptOptions, setDeptOptions] = useState<string[]>([]);

  const [departments, setDepartments] = useState<string[]>([]);
  const [department, setDepartment] = useState('');
  const [emkScopeMode, setEmkScopeMode] = useState<EmkScopeMode>('single');
  const [emkSummaryMode, setEmkSummaryMode] = useState<EmkSummaryMode>('all');
  const [emkSelectedDepartments, setEmkSelectedDepartments] = useState<string[]>([]);
  const [emkAsOf, setEmkAsOf] = useState<string>(() => todayIso());
  const [emkFile, setEmkFile] = useState<string | null>(null);
  const [emk, setEmk] = useState<EmkAnalysis | null>(null);
  const [emkSub, setEmkSub] = useState<'share' | 'violations' | 'doctors' | 'skp' | 'age'>('share');
  const [emkSplitSnils, setEmkSplitSnils] = useState(false);

  const [ksgFiles, setKsgFiles] = useState<KsgFile[]>([]);
  const [ksgActive, setKsgActive] = useState(0);
  const [ksg, setKsg] = useState<KsgAnalysis | null>(null);
  const [ksgRef, setKsgRef] = useState('');
  const [ksgSub, setKsgSub] = useState<'doctors' | 'cases' | 'ops' | 'departments' | 'compare'>('doctors');
  const [ksgDepartments, setKsgDepartments] = useState<string[]>([]);
  const [ksgDepartment, setKsgDepartment] = useState('');
  const [ksgScopeMode, setKsgScopeMode] = useState<EmkScopeMode>('summary');
  const [ksgSummaryMode, setKsgSummaryMode] = useState<EmkSummaryMode>('all');
  const [ksgSelectedDepartments, setKsgSelectedDepartments] = useState<string[]>([]);
  const [ksgPeriod, setKsgPeriod] = useState('all');
  const [ksgPeriods, setKsgPeriods] = useState<{ id: string; label: string }[]>([]);
  const [ksgSource, setKsgSource] = useState<'ksg' | 'other'>('ksg');
  const [ksgHasOther, setKsgHasOther] = useState(false);
  const [ksgCompareMode, setKsgCompareMode] = useState<'months' | 'departments'>('months');
  const [ksgCompareDepartments, setKsgCompareDepartments] = useState<string[]>([]);
  const [opsFile, setOpsFile] = useState<string | null>(null);
  const [ops, setOps] = useState<OpsAnalysis | null>(null);
  const [opsDepartments, setOpsDepartments] = useState<string[]>([]);
  const [opsDepartment, setOpsDepartment] = useState('');
  const [opsScopeMode, setOpsScopeMode] = useState<EmkScopeMode>('single');
  const [opsSummaryMode, setOpsSummaryMode] = useState<EmkSummaryMode>('all');
  const [opsSelectedDepartments, setOpsSelectedDepartments] = useState<string[]>([]);
  const [opsSub, setOpsSub] = useState<'long' | 'table'>('long');
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [compareIndices, setCompareIndices] = useState<number[]>([]);
  const [compareCharts, setCompareCharts] = useState<CompareChartsState>(DEFAULT_COMPARE_CHARTS);
  const [dragOver, setDragOver] = useState(false);
  const [copyFlash, setCopyFlash] = useState(false);
  const [loadMappingHint, setLoadMappingHint] = useState<string | null>(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [whatsNewOpen, setWhatsNewOpen] = useState(false);
  const [changelog, setChangelog] = useState<ChangelogEntry[]>([]);
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
              last_main_tab: tab === 'ksg' ? 1 : tab === 'ops' ? 2 : 0,
              ui_prefs: {
                main_tab: tab,
                emk_sub: emkSub,
                ksg_sub: ksgSub,
                ops_sub: opsSub,
                compare_charts: compareCharts,
                emk_scope_mode: emkScopeMode,
                emk_summary_mode: emkSummaryMode,
                emk_selected_departments: emkSelectedDepartments,
                ksg_scope_mode: ksgScopeMode,
                ksg_summary_mode: ksgSummaryMode,
                ksg_selected_departments: ksgSelectedDepartments,
                ksg_period: ksgPeriod,
                ksg_source: ksgSource,
                ksg_compare_mode: ksgCompareMode,
                ops_scope_mode: opsScopeMode,
                ops_summary_mode: opsSummaryMode,
                ops_selected_departments: opsSelectedDepartments,
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
  }, [
    tab,
    emkSub,
    ksgSub,
    opsSub,
    compareCharts,
    emkScopeMode,
    emkSummaryMode,
    emkSelectedDepartments,
    ksgScopeMode,
    ksgSummaryMode,
    ksgSelectedDepartments,
    ksgPeriod,
    ksgSource,
    ksgCompareMode,
    opsScopeMode,
    opsSummaryMode,
    opsSelectedDepartments,
  ]);

  useEffect(() => {
    if (ksgScopeMode === 'single' && ksgCompareMode === 'departments') {
      setKsgCompareMode('months');
      setCompare(null);
    }
  }, [ksgScopeMode, ksgCompareMode]);

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
        if (prefs?.main_tab === 'ksg' || prefs?.main_tab === 'emk' || prefs?.main_tab === 'ops') {
          setTab(prefs.main_tab);
        } else if (cfgRes.config?.last_main_tab === 1) {
          setTab('ksg');
        } else if (cfgRes.config?.last_main_tab === 2) {
          setTab('ops');
        }
        const emkSubs = ['share', 'violations', 'doctors', 'skp', 'age'] as const;
        if (prefs?.emk_sub && (emkSubs as readonly string[]).includes(prefs.emk_sub)) {
          setEmkSub(prefs.emk_sub as typeof emkSubs[number]);
        }
        const ksgSubs = ['doctors', 'cases', 'ops', 'departments', 'compare'] as const;
        if (prefs?.ksg_sub && (ksgSubs as readonly string[]).includes(prefs.ksg_sub)) {
          setKsgSub(prefs.ksg_sub as typeof ksgSubs[number]);
        }
        const opsSubs = ['long', 'table'] as const;
        if (prefs?.ops_sub && (opsSubs as readonly string[]).includes(prefs.ops_sub)) {
          setOpsSub(prefs.ops_sub as typeof opsSubs[number]);
        }
        if (prefs?.compare_charts) {
          setCompareCharts({ ...DEFAULT_COMPARE_CHARTS, ...prefs.compare_charts });
        }
        if (prefs?.emk_scope_mode === 'single' || prefs?.emk_scope_mode === 'summary') {
          setEmkScopeMode(prefs.emk_scope_mode);
        }
        if (prefs?.emk_summary_mode === 'all' || prefs?.emk_summary_mode === 'multi') {
          setEmkSummaryMode(prefs.emk_summary_mode);
        }
        if (Array.isArray(prefs?.emk_selected_departments)) {
          setEmkSelectedDepartments(prefs.emk_selected_departments.filter(Boolean));
        }
        if (prefs?.ops_scope_mode === 'single' || prefs?.ops_scope_mode === 'summary') {
          setOpsScopeMode(prefs.ops_scope_mode);
        }
        if (prefs?.ops_summary_mode === 'all' || prefs?.ops_summary_mode === 'multi') {
          setOpsSummaryMode(prefs.ops_summary_mode);
        }
        if (Array.isArray(prefs?.ops_selected_departments)) {
          setOpsSelectedDepartments(prefs.ops_selected_departments.filter(Boolean));
        }
        if (prefs?.ksg_scope_mode === 'single' || prefs?.ksg_scope_mode === 'summary') {
          setKsgScopeMode(prefs.ksg_scope_mode);
        }
        if (prefs?.ksg_summary_mode === 'all' || prefs?.ksg_summary_mode === 'multi') {
          setKsgSummaryMode(prefs.ksg_summary_mode);
        }
        if (Array.isArray(prefs?.ksg_selected_departments)) {
          setKsgSelectedDepartments(prefs.ksg_selected_departments.filter(Boolean));
        }
        if (typeof prefs?.ksg_period === 'string' && prefs.ksg_period) {
          setKsgPeriod(prefs.ksg_period);
        }
        if (prefs?.ksg_source === 'other' || prefs?.ksg_source === 'ksg') {
          setKsgSource(prefs.ksg_source);
        }
        if (prefs?.ksg_compare_mode === 'months' || prefs?.ksg_compare_mode === 'departments') {
          setKsgCompareMode(prefs.ksg_compare_mode);
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

  const syncMenuState = useCallback(async (cfg?: AppConfig) => {
    const sync = api().syncMenuState;
    if (!sync) return;
    const source = cfg || config;
    await sync({
      recent_emk: source.recent_emk || [],
      recent_ksg: source.recent_ksg || [],
      recent_ops: source.recent_ops || [],
      date_format: source.date_format || 'dayfirst',
    });
  }, [config]);

  const refreshConfig = useCallback(async () => {
    try {
      const res = await rpc<{ config: AppConfig }>('config.get');
      setConfig(res.config || {});
      await syncMenuState(res.config);
      return res.config;
    } catch {
      return null;
    }
  }, [syncMenuState]);

  useEffect(() => {
    if (!prefsReady.current) return;
    void syncMenuState(config);
  }, [config, syncMenuState]);

  const toggleTheme = useCallback(async () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try {
      const res = await rpc<{ config: AppConfig }>('config.set', {
        config: { theme: next === 'dark' ? 'slice-dark' : 'slice-light' },
      });
      setConfig(res.config);
      await syncMenuState(res.config);
    } catch {
      // local only
    }
  }, [theme, syncMenuState]);

  const runEmkAnalyze = useCallback(
    async (opts?: {
      scope?: EmkScope;
      department?: string;
      departments?: string[];
      scopeMode?: EmkScopeMode;
      summaryMode?: EmkSummaryMode;
      asOf?: string;
    }) => {
      if (!emkFile) return;
      const nextScopeMode = opts?.scopeMode ?? emkScopeMode;
      const nextSummaryMode = opts?.summaryMode ?? emkSummaryMode;
      const nextDepartment = opts?.department ?? department;
      const nextSelected = opts?.departments ?? emkSelectedDepartments;
      const nextAsOf = opts?.asOf ?? emkAsOf;

      let scope: EmkScope = opts?.scope ?? 'single';
      let analyzeDepartment = nextDepartment;
      let analyzeDepartments = nextSelected;

      if (!opts?.scope) {
        if (nextScopeMode === 'summary') {
          if (nextSummaryMode === 'all') {
            scope = 'all';
          } else {
            scope = 'multi';
            analyzeDepartments = nextSelected;
          }
        } else {
          scope = 'single';
          analyzeDepartment = nextDepartment;
        }
      }

      if (scope === 'multi' && !analyzeDepartments.length) {
        setError('Выберите хотя бы одно отделение');
        return;
      }

      setBusy(true);
      setError(null);
      try {
        setStatus('Анализ ЭМК…');
        const params: Record<string, unknown> = { scope };
        if (scope === 'single') params.department = analyzeDepartment;
        if (scope === 'multi') params.departments = analyzeDepartments;
        if (nextAsOf) params.as_of = nextAsOf;
        const analysis = await rpc<EmkAnalysis>('emk.analyze', params);
        setEmk(analysis);
        setEmkScopeMode(nextScopeMode);
        setEmkSummaryMode(nextSummaryMode);
        if (scope === 'multi') setEmkSelectedDepartments(analyzeDepartments);
        if (analysis.as_of) setEmkAsOf(isoFromEmkDate(analysis.as_of));
        const asOfLabel = analysis.as_of ? ` · на ${fmtDateRu(analysis.as_of)}` : '';
        setStatus(
          `ЭМК: ${analysis.file_name || emkFile} · ${analysis.department || '—'}${asOfLabel}`,
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [
      emkFile,
      emkScopeMode,
      emkSummaryMode,
      department,
      emkSelectedDepartments,
      emkAsOf,
    ],
  );

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
        profile_id?: string;
        profile_name?: string;
        mapping?: ColumnMapping;
        emk_variant?: string;
        emk_variant_label?: string;
      }>('emk.load', { path });
      setEmkFile(loaded.file_name);
      setDepartments(loaded.departments);
      if (loaded.known_departments?.length) setDeptOptions(loaded.known_departments);
      else setDeptOptions(loaded.departments);
      const dept = loaded.preferred_department || loaded.departments[0] || '';
      setDepartment(dept);
      setEmkScopeMode('single');
      setEmkSummaryMode('all');
      setEmkSelectedDepartments([]);
      const asOf = todayIso();
      setEmkAsOf(asOf);
      setStatus('Анализ ЭМК…');
      const analysis = await rpc<EmkAnalysis>('emk.analyze', {
        scope: 'single',
        department: dept,
        as_of: asOf,
      });
      setEmk(analysis);
      if (analysis.as_of) setEmkAsOf(isoFromEmkDate(analysis.as_of));
      setTab('emk');
      const mapHint = mappingStatusSuffix(loaded.profile_name, loaded.mapping);
      setLoadMappingHint(mapHint);
      const variantHint = loaded.emk_variant_label || analysis.emk_variant_label;
      setStatus(
        variantHint
          ? `ЭМК (${variantHint}): ${loaded.file_name} · ${mapHint}`
          : `ЭМК: ${loaded.file_name} · ${mapHint}`,
      );
      await refreshConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus('Ошибка загрузки ЭМК');
    } finally {
      setBusy(false);
    }
  }, [refreshConfig]);

  const loadEmk = useCallback(async () => {
    const path = await api().openExcelDialog({ title: 'Файл ЭМК' });
    if (!path || Array.isArray(path)) return;
    await loadEmkFromPath(path);
  }, [loadEmkFromPath]);

  const reanalyzeEmk = useCallback(
    async (dept: string) => {
      setDepartment(dept);
      await runEmkAnalyze({
        scope: 'single',
        department: dept,
        scopeMode: 'single',
      });
    },
    [runEmkAnalyze],
  );

  const runKsgAnalyze = useCallback(
    async (overrides?: {
      scope?: EmkScope;
      scopeMode?: EmkScopeMode;
      summaryMode?: EmkSummaryMode;
      department?: string;
      departments?: string[];
      period?: string;
      source?: 'ksg' | 'other';
    }) => {
      if (!ksgFiles.length) return;
      setBusy(true);
      setError(null);
      try {
        const scopeMode = overrides?.scopeMode ?? ksgScopeMode;
        const summaryMode = overrides?.summaryMode ?? ksgSummaryMode;
        let scope: EmkScope = overrides?.scope ?? 'all';
        let department = overrides?.department ?? ksgDepartment;
        let departments = overrides?.departments ?? ksgSelectedDepartments;
        if (scopeMode === 'single') {
          scope = 'single';
          department = overrides?.department ?? ksgDepartment;
        } else if (summaryMode === 'all') {
          scope = 'all';
        } else {
          scope = 'multi';
          departments = overrides?.departments ?? ksgSelectedDepartments;
        }
        const period = overrides?.period ?? ksgPeriod;
        const source = overrides?.source ?? ksgSource;
        const res = await rpc<{ analysis: KsgAnalysis }>('ksg.analyze', {
          scope,
          department,
          departments,
          period,
          source,
        });
        setKsg(res.analysis);
        if (res.analysis.departments?.length) {
          setKsgDepartments(res.analysis.departments);
          setDeptOptions((prev) => {
            const merged = [...prev];
            for (const d of res.analysis.departments || []) {
              if (d && !merged.includes(d)) merged.push(d);
            }
            return merged;
          });
        }
        if (res.analysis.periods?.length) setKsgPeriods(res.analysis.periods);
        if (typeof res.analysis.has_other_services === 'boolean') {
          setKsgHasOther(res.analysis.has_other_services);
        }
        setCompare(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [
      ksgFiles.length,
      ksgScopeMode,
      ksgSummaryMode,
      ksgDepartment,
      ksgSelectedDepartments,
      ksgPeriod,
      ksgSource,
    ],
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
      let lastProfile: string | undefined;
      let lastMapping: ColumnMapping | undefined;
      for (const path of list) {
        setStatus(`Загрузка КСГ: ${path.split(/[/\\]/).pop()}`);
        const res = await rpc<{
          files: KsgFile[];
          active: number;
          reference_status: string;
          analysis: KsgAnalysis;
          departments?: string[];
          preferred_department?: string;
          periods?: { id: string; label: string }[];
          has_other_services?: boolean;
          profile_id?: string;
          profile_name?: string;
          mapping?: ColumnMapping;
        }>('ksg.load', { path });
        files = res.files;
        active = res.active;
        ref = res.reference_status;
        lastAnalysis = res.analysis;
        lastProfile = res.profile_name;
        lastMapping = res.mapping;
        if (res.departments?.length) {
          setKsgDepartments(res.departments);
          setDeptOptions((prev) => {
            const merged = [...prev];
            for (const d of res.departments || []) {
              if (d && !merged.includes(d)) merged.push(d);
            }
            return merged;
          });
        }
        if (res.preferred_department) setKsgDepartment(res.preferred_department);
        if (res.periods?.length) {
          setKsgPeriods(res.periods);
          setKsgPeriod(res.periods.length === 1 ? res.periods[0].id : 'all');
        } else {
          setKsgPeriod('all');
        }
        setKsgScopeMode('summary');
        setKsgSummaryMode('all');
        setKsgSource('ksg');
        setKsgHasOther(!!res.has_other_services);
        setKsgCompareDepartments(res.departments || []);
      }
      setKsgFiles(files);
      setKsgActive(active);
      setKsgRef(ref);
      setKsg(lastAnalysis);
      setCompare(null);
      setTab('ksg');
      const mapHint = mappingStatusSuffix(lastProfile, lastMapping);
      setLoadMappingHint(mapHint);
      setStatus(`КСГ: ${files.length} файл(ов) · ${mapHint}`);
      await refreshConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus('Ошибка загрузки КСГ');
    } finally {
      setBusy(false);
    }
  }, [refreshConfig]);

  const loadKsg = useCallback(async () => {
    const paths = await api().openExcelDialog({
      title: 'Файлы КСГ',
      multiSelections: true,
    });
    const list = Array.isArray(paths) ? paths : paths ? [paths] : [];
    await loadKsgFromPaths(list);
  }, [loadKsgFromPaths]);

  const loadOpsFromPath = useCallback(async (path: string) => {
    setError(null);
    setBusy(true);
    try {
      setStatus('Загрузка операций…');
      const loaded = await rpc<
        OpsAnalysis & {
          profile_id?: string;
          profile_name?: string;
          mapping?: ColumnMapping;
          preferred_department?: string;
          known_departments?: string[];
        }
      >('ops.load', { path });
      setOpsFile(loaded.file_name || path.split(/[/\\]/).pop() || path);
      const deps = loaded.departments || [];
      setOpsDepartments(deps);
      const dept = loaded.preferred_department || loaded.department || deps[0] || '';
      setOpsDepartment(dept);
      setOpsScopeMode('single');
      if (loaded.known_departments?.length) setDeptOptions(loaded.known_departments);
      setOps(loaded);
      setTab('ops');
      const mapHint = mappingStatusSuffix(loaded.profile_name, loaded.mapping);
      setLoadMappingHint(mapHint);
      setStatus(`Операции: ${loaded.file_name || 'файл'} · ${mapHint}`);
      await refreshConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus('Ошибка загрузки операций');
    } finally {
      setBusy(false);
    }
  }, [refreshConfig]);

  const loadOps = useCallback(async () => {
    const path = await api().openExcelDialog({ title: 'Отчёт по операциям' });
    if (!path || Array.isArray(path)) return;
    await loadOpsFromPath(path);
  }, [loadOpsFromPath]);

  const runOpsAnalyze = useCallback(
    async (opts?: {
      scope?: EmkScope;
      department?: string;
      departments?: string[];
      scopeMode?: EmkScopeMode;
      summaryMode?: EmkSummaryMode;
    }) => {
      if (!opsFile) return;
      const nextScopeMode = opts?.scopeMode ?? opsScopeMode;
      const nextSummaryMode = opts?.summaryMode ?? opsSummaryMode;
      const nextDepartment = opts?.department ?? opsDepartment;
      const nextSelected = opts?.departments ?? opsSelectedDepartments;

      let scope: EmkScope = opts?.scope ?? 'single';
      let analyzeDepartment = nextDepartment;
      let analyzeDepartments = nextSelected;

      if (!opts?.scope) {
        if (nextScopeMode === 'summary') {
          if (nextSummaryMode === 'all') {
            scope = 'all';
          } else {
            scope = 'multi';
            analyzeDepartments = nextSelected;
          }
        } else {
          scope = 'single';
          analyzeDepartment = nextDepartment;
        }
      }

      if (scope === 'multi' && !analyzeDepartments.length) {
        setError('Выберите хотя бы одно отделение');
        return;
      }

      setBusy(true);
      setError(null);
      try {
        setStatus('Анализ операций…');
        const params: Record<string, unknown> = { scope };
        if (scope === 'single') params.department = analyzeDepartment;
        if (scope === 'multi') params.departments = analyzeDepartments;
        const analysis = await rpc<OpsAnalysis>('ops.analyze', params);
        setOps(analysis);
        setOpsScopeMode(nextScopeMode);
        setOpsSummaryMode(nextSummaryMode);
        if (scope === 'single' && opts?.department !== undefined) {
          setOpsDepartment(opts.department);
        } else if (scope === 'single' && analysis.department && nextScopeMode === 'single') {
          // keep single-dept select in sync when label is a real department name
          if (opsDepartments.includes(analysis.department)) {
            setOpsDepartment(analysis.department);
          }
        }
        if (scope === 'multi') setOpsSelectedDepartments(analyzeDepartments);
        if (analysis.departments?.length) setOpsDepartments(analysis.departments);
        setStatus(
          `Операции: ${analysis.file_name || opsFile} · ${analysis.department || '—'}`,
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [
      opsFile,
      opsScopeMode,
      opsSummaryMode,
      opsDepartment,
      opsSelectedDepartments,
      opsDepartments,
    ],
  );

  const reanalyzeOps = useCallback(
    async (dept?: string) => {
      if (dept !== undefined) {
        setOpsDepartment(dept);
        await runOpsAnalyze({
          scope: 'single',
          scopeMode: 'single',
          department: dept,
        });
        return;
      }
      await runOpsAnalyze();
    },
    [runOpsAnalyze],
  );

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
    setBusy(true);
    setError(null);
    try {
      if (ksgCompareMode === 'departments') {
        const departments = ksgCompareDepartments;
        if (departments.length < 2) {
          setError('Для сравнения отделений выберите минимум 2');
          return;
        }
        const res = await rpc<CompareResult>('ksg.compare', {
          mode: 'departments',
          departments,
          period: ksgPeriod,
          source: ksgSource,
        });
        setCompare(res);
        setKsgSub('compare');
        return;
      }
      const indices = compareIndices.length ? compareIndices : ksgFiles.map((_, i) => i);
      if (indices.length < 2) {
        setError('Для сравнения выберите минимум 2 файла КСГ');
        return;
      }
      const res = await rpc<CompareResult>('ksg.compare', { indices, mode: 'months' });
      setCompare(res);
      setKsgSub('compare');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [
    compareIndices,
    ksgFiles,
    ksgCompareMode,
    ksgCompareDepartments,
    ksgDepartments,
    ksgPeriod,
    ksgSource,
  ]);

  const copySummary = useCallback(async () => {
    const lines: string[] = [];
    if (tab === 'emk' && emk) {
      const period =
        emk.period_start || emk.period_end
          ? `${fmtDateRu(emk.period_start)} — ${fmtDateRu(emk.period_end)}`
          : null;
      lines.push(period ? `Сводка ЭМК за ${period}` : 'Сводка ЭМК');
      if (emk.emk_variant === 'current') {
        lines.push(`Тип: текущие пациенты на ${fmtDateRu(emk.as_of || emk.period_end)}`);
      }
      lines.push(`Отделение: ${emk.department || department || '—'}`);
      if (emk.scope && emk.scope !== 'single' && emk.departments_in_scope?.length) {
        lines.push(`В сводке: ${emk.departments_in_scope.length} отделений`);
      }
      lines.push(`Пациентов выписано: ${fmtNum(emk.total_patients)}`);
      lines.push(`Средний койко-день: ${fmtNum(emk.avg_beddays, 1)}`);
      lines.push(`Экстренные: ${fmtNum(emk.urgent)}`);
      lines.push(`Плановые: ${fmtNum(emk.planned)}`);
      lines.push(`Нарушения всего: ${fmtNum(emk.violations_total)}`);
      lines.push(`СКП: ${fmtNum(emk.skp_count)}`);
    } else if (tab === 'ksg' && ksg) {
      lines.push('Сводка КСГ');
      lines.push(`Файл: ${ksgFiles[ksgActive]?.label || ksgFiles[ksgActive]?.name || '—'}`);
      if (ksg.department) lines.push(`Отделение: ${ksg.department}`);
      if (ksg.period_label) lines.push(`Период: ${ksg.period_label}`);
      if (ksg.source === 'other') lines.push('Источник: др. услуги');
      lines.push(`Пациенты: ${fmtNum(ksg.total_patients)}`);
      lines.push(`Сумма: ${fmtNum(ksg.total_sum, 0)}`);
      lines.push(`Средний КЗ: ${fmtNum(ksg.avg_kz_total, 3)}`);
      lines.push(`Без услуги: ${fmtNum(ksg.no_service?.length)}`);
      lines.push(`КСЛП: ${fmtNum(ksg.kslp_issues?.length)}`);
      if (ksg.policy_check_enabled) {
        lines.push(`Полис / СМО: ${fmtNum(ksg.policy_issues?.length ?? ksg.total_policy_issues)}`);
      }
    } else if (tab === 'ops' && ops) {
      lines.push('Сводка операций');
      lines.push(`Файл: ${ops.file_name || opsFile || '—'}`);
      lines.push(`Отделение: ${ops.department || opsDepartment || '—'}`);
      lines.push(`Всего операций: ${fmtNum(ops.total_ops)}`);
      lines.push(`Длительных (>${ops.long_op_hours} ч): ${fmtNum(ops.long_count)}`);
      lines.push(`Без опер.стола: ${fmtNum(ops.missing_table_count)}`);
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
  }, [tab, emk, department, ksg, ksgFiles, ksgActive, ops, opsFile, opsDepartment]);

  const menuOpen = useCallback(async () => {
    if (tab === 'ops') await loadOps();
    else if (tab === 'ksg') await loadKsg();
    else await loadEmk();
  }, [tab, loadEmk, loadKsg, loadOps]);

  const menuSave = useCallback(() => {
    const canSave =
      (tab === 'emk' && emk) || (tab === 'ksg' && ksg) || (tab === 'ops' && ops);
    if (!canSave) {
      setError('Нет данных для сохранения отчёта');
      return;
    }
    setExportOpen(true);
  }, [tab, emk, ksg, ops]);

  const menuCheckUpdates = useCallback(async () => {
    const repo = (config.github_repo || '').trim();
    if (!repo) {
      setError('Укажите репозиторий GitHub в настройках (owner/repo).');
      setSettingsOpen(true);
      return;
    }
    try {
      await api().openExternal(`https://github.com/${repo}/releases/latest`);
      setStatus('Открыта страница обновлений на GitHub');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [config.github_repo]);

  const menuWhatsNew = useCallback(async () => {
    try {
      const res = await rpc<{ entries: ChangelogEntry[] }>('app.changelog');
      setChangelog(res.entries || []);
      setWhatsNewOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const menuDateFormat = useCallback(
    async (value: 'dayfirst' | 'monthfirst') => {
      try {
        const res = await rpc<{ config: AppConfig }>('config.set', {
          config: { date_format: value },
        });
        setConfig(res.config);
        setStatus('Формат даты изменён. Перезагрузите данные для применения.');
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [],
  );

  useEffect(() => {
    const subscribe = api().onMenuAction;
    if (!subscribe) return undefined;
    return subscribe(({ action, payload }) => {
      void (async () => {
        switch (action) {
          case 'open':
            await menuOpen();
            break;
          case 'save':
            menuSave();
            break;
          case 'copy-selection':
            if (copySelectionFromDocument()) {
              setStatus('Выделенное скопировано');
            } else {
              setError('Нет выделенного текста для копирования');
            }
            break;
          case 'copy-summary':
            await copySummary();
            break;
          case 'settings':
            setSettingsOpen(true);
            break;
          case 'toggle-theme':
            await toggleTheme();
            break;
          case 'check-updates':
            await menuCheckUpdates();
            break;
          case 'whats-new':
            await menuWhatsNew();
            break;
          case 'about':
            setAboutOpen(true);
            break;
          case 'log-missing':
            setStatus('Файл лога ещё не создан.');
            break;
          case 'date-format': {
            const value = payload?.value;
            if (value === 'dayfirst' || value === 'monthfirst') {
              await menuDateFormat(value);
            }
            break;
          }
          case 'open-recent': {
            const kind = payload?.kind;
            const filePath = payload?.path;
            if (typeof filePath !== 'string' || !filePath) return;
            const approve = api().approveLoadPaths;
            const approved = approve ? await approve([filePath]) : [filePath];
            if (!approved.length) {
              setError('Не удалось открыть файл из списка недавних');
              return;
            }
            if (kind === 'ksg') await loadKsgFromPaths(approved);
            else if (kind === 'ops') await loadOpsFromPath(approved[0]);
            else await loadEmkFromPath(approved[0]);
            break;
          }
          default:
            break;
        }
      })();
    });
  }, [
    menuOpen,
    menuSave,
    copySummary,
    toggleTheme,
    menuCheckUpdates,
    menuWhatsNew,
    menuDateFormat,
    loadEmkFromPath,
    loadKsgFromPaths,
    loadOpsFromPath,
  ]);

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
      const approve = api().approveLoadPaths;
      const approved = approve ? await approve(paths) : paths;
      if (!approved.length) {
        setError('Не удалось подтвердить пути файлов');
        return;
      }
      if (tab === 'ops') {
        await loadOpsFromPath(approved[0]);
      } else if (tab === 'ksg' || approved.length > 1) {
        await loadKsgFromPaths(approved);
      } else {
        await loadEmkFromPath(approved[0]);
      }
    },
    [tab, loadEmkFromPath, loadKsgFromPaths, loadOpsFromPath],
  );

  const doExport = useCallback(
    async (opts: { format: 'xlsx' | 'txt'; sections?: Record<string, boolean> }) => {
      const method =
        tab === 'emk' ? 'emk.export' : tab === 'ops' ? 'ops.export' : 'ksg.export';
      const defaultName =
        tab === 'emk'
          ? `${emk?.report_basename || 'Отчет ЭМК'}.${opts.format}`
          : tab === 'ops'
            ? `Проверки_операций.${opts.format}`
            : `Отчет_КСГ_${ksgFiles[ksgActive]?.label || 'файл'}.${opts.format}`;
      const path =
        opts.format === 'xlsx'
          ? await api().saveExcelDialog({ defaultPath: defaultName })
          : await api().saveTextDialog({ defaultPath: defaultName });
      if (!path) return;
      setStatus('Сохранение…');
      const res = await rpc<{ path: string }>(method, {
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

  const ksgCaseRows = useCallback(
    (rows: Record<string, unknown>[] | undefined) =>
      normalizeKsgCaseRows(rows || []),
    [],
  );

  const emkShow = useCallback(
    (key: string) => config.emk_display?.[key] !== false,
    [config.emk_display],
  );
  const ksgShow = useCallback(
    (key: string) => config.ksg_display?.[key] !== false,
    [config.ksg_display],
  );

  const snilsSplitOn = Boolean(emkSplitSnils && emk?.snils_available);

  const shareBars = useMemo((): BarItem[] => {
    if (!emk?.violation_share?.length) return [];
    return emk.violation_share
      .map((row) => {
        const label = String(row['Тип нарушения'] ?? '');
        return {
          label,
          value: Number(row['Доля, %'] ?? 0),
          color: VIOLATION_COLORS[label],
        };
      })
      .sort((a, b) => b.value - a.value);
  }, [emk]);

  const shareTableRows = useMemo(() => {
    if (!emk) return [];
    if (snilsSplitOn && emk.violation_share_by_snils?.length) {
      return [...emk.violation_share_by_snils].sort(
        (a, b) => Number(b['Всего'] ?? 0) - Number(a['Всего'] ?? 0),
      );
    }
    return [...(emk.violation_share || [])].sort(
      (a, b) => Number(b['Количество'] ?? 0) - Number(a['Количество'] ?? 0),
    );
  }, [emk, snilsSplitOn]);

  const coverageBars = useMemo((): BarItem[] => {
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

  const coverageGroups = useMemo((): BarGroup[] => {
    if (!emk?.cases_coverage_by_snils) return [];
    const c = emk.cases_coverage_by_snils;
    const build = (
      label: string,
      withVal: number,
      withoutVal: number,
      withColor: string,
      withoutColor: string,
    ): BarGroup => {
      const series: BarGroup['series'] = [];
      if (withVal > 0) series.push({ key: 'with', value: withVal, color: withColor });
      if (withoutVal > 0) series.push({ key: 'without', value: withoutVal, color: withoutColor });
      // Группу «Без нарушений» / «С нарушениями» всегда показываем; если всё 0 — пустой столбец
      if (!series.length) {
        series.push({ key: 'with', value: 0, color: withColor });
      }
      return { label, series };
    };
    return [
      build(
        'С нарушениями',
        Number(c.with_violations_snils ?? 0),
        Number(c.with_violations_no_snils ?? 0),
        'var(--danger)',
        '#c45c5c',
      ),
      build(
        'Без нарушений',
        Number(c.without_violations_snils ?? 0),
        Number(c.without_violations_no_snils ?? 0),
        'var(--ok)',
        '#6a9b7a',
      ),
    ];
  }, [emk]);

  const coverageTableRows = useMemo(() => {
    if (!emk) return [];
    if (snilsSplitOn && emk.cases_coverage_by_snils) {
      const c = emk.cases_coverage_by_snils;
      return [
        {
          Группа: 'С нарушениями',
          'С СНИЛС': c.with_violations_snils,
          'Без СНИЛС': c.with_violations_no_snils,
          Всего: c.with_violations_snils + c.with_violations_no_snils,
        },
        {
          Группа: 'Без нарушений',
          'С СНИЛС': c.without_violations_snils,
          'Без СНИЛС': c.without_violations_no_snils,
          Всего: c.without_violations_snils + c.without_violations_no_snils,
        },
      ];
    }
    return [
      { Группа: 'С нарушениями', Количество: emk.cases_with_violations ?? 0 },
      { Группа: 'Без нарушений', Количество: emk.cases_without_violations ?? 0 },
    ];
  }, [emk, snilsSplitOn]);

  const ageBars = useMemo(() => {
    if (!emk?.age_dist) return [];
    return Object.entries(emk.age_dist).map(([label, value]) => ({
      label,
      value: Number(value) || 0,
    }));
  }, [emk]);

  const violTypeRows = useMemo((): ViolationTypeRow[] => {
    if (!emk?.violations?.length || !violTypeOpen) return [];
    return emk.violations
      .filter((r) => String(r['тип_нарушения'] ?? '') === violTypeOpen)
      .map((r) => ({
        КВС: String(r['КВС'] ?? ''),
        пометка: String(r['пометка'] ?? ''),
        врач: formatShortPersonName(r['врач']),
        нарушение: String(r['нарушение'] ?? ''),
      }));
  }, [emk, violTypeOpen]);

  const coverageListRows = useMemo((): ViolationTypeRow[] => {
    if (!emk?.cases_coverage_lists || !coverageListOpen) return [];
    const raw = emk.cases_coverage_lists[
      coverageListOpen.key as keyof NonNullable<EmkAnalysis['cases_coverage_lists']>
    ];
    if (!raw?.length) return [];
    return raw.map((r) => ({
      КВС: String(r['КВС'] ?? ''),
      пометка: String(r['пометка'] ?? ''),
      врач: formatShortPersonName(r['врач']),
      нарушений: Number(r['нарушений'] ?? 0),
    }));
  }, [emk, coverageListOpen]);

  const openViolationType = useCallback((typeLabel: string) => {
    setCoverageListOpen(null);
    setViolTypeOpen(typeLabel);
  }, []);

  const openViolationTypeInTable = useCallback((typeLabel: string) => {
    setViolTypeOpen(null);
    setEmkSub('violations');
    setViolTableFilter(typeLabel);
    setViolTableFilterKey((k) => k + 1);
  }, []);

  const openCoverageList = useCallback((title: string, listKey: string) => {
    setViolTypeOpen(null);
    setCoverageListOpen({ title, key: listKey });
  }, []);

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
          <button
            className="btn btn-ghost"
            type="button"
            title="Открыть настройки приложения"
            onClick={() => setSettingsOpen(true)}
          >
            Настройки
          </button>
          <button
            className="btn btn-ghost"
            type="button"
            title={theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
            onClick={toggleTheme}
          >
            {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={`tab ${tab === 'emk' ? 'active' : ''}`}
          title="Анализ заполнения историй болезни (ЭМК)"
          onClick={() => setTab('emk')}
        >
          Анализ ЭМК
        </button>
        <button
          type="button"
          className={`tab ${tab === 'ksg' ? 'active' : ''}`}
          title="Анализ отчётов КСГ по месяцам"
          onClick={() => setTab('ksg')}
        >
          Анализ КСГ
        </button>
        <button
          type="button"
          className={`tab ${tab === 'ops' ? 'active' : ''}`}
          title="Проверки длительных операций и опер. стола"
          onClick={() => setTab('ops')}
        >
          Операции
        </button>
      </nav>

      <main className="workspace">
        {error && (
          <div
            className={
              /не тот отчёт|не тот тип отчёта/i.test(error) ? 'info-banner' : 'error-banner'
            }
          >
            {error}
          </div>
        )}
        {!error && loadMappingHint && (emk || ksgFiles.length > 0 || ops) && (
          <div className="mapping-banner">{loadMappingHint}</div>
        )}

        {tab === 'emk' && (
          <>
            <div className="toolbar">
              <button
                className="btn btn-primary"
                type="button"
                disabled={busy}
                title="Выбрать Excel-отчёт по заполнению ЭМК"
                onClick={loadEmk}
              >
                Загрузить Excel
              </button>
              <span className="muted toolbar-profile" title="Активный профиль формата ЭМК">
                {activeProfileLabel(config, 'emk')}
              </span>
              <button
                className="btn"
                type="button"
                disabled={busy || !emk}
                title="Сохранить результаты анализа ЭМК в файл"
                onClick={() => setExportOpen(true)}
              >
                Сохранить…
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !emk}
                title="Скопировать краткую сводку ЭМК в буфер обмена"
                onClick={() => void copySummary()}
              >
                {copyFlash && tab === 'emk' ? 'Скопировано' : 'Копировать сводку'}
              </button>
              <button
                className="btn btn-accent"
                type="button"
                disabled={busy || !emk || !(emk.violations_total > 0)}
                title="Открыть текстовую сводку нарушений для копирования"
                onClick={() => setViolOpen(true)}
              >
                Сводка нарушений
              </button>
              {departments.length > 0 && (
                <EmkDepartmentScope
                  departments={departments}
                  singleDepartment={department}
                  onSingleDepartmentChange={(value) => void reanalyzeEmk(value)}
                  scopeMode={emkScopeMode}
                  onScopeModeChange={(mode) => {
                    setEmkScopeMode(mode);
                    if (mode === 'summary') {
                      if (emkSummaryMode === 'all') {
                        void runEmkAnalyze({ scopeMode: 'summary', summaryMode: 'all', scope: 'all' });
                      } else if (emkSelectedDepartments.length) {
                        void runEmkAnalyze({
                          scopeMode: 'summary',
                          summaryMode: 'multi',
                          scope: 'multi',
                          departments: emkSelectedDepartments,
                        });
                      }
                    } else if (department) {
                      void reanalyzeEmk(department);
                    }
                  }}
                  summaryMode={emkSummaryMode}
                  onSummaryModeChange={(mode) => {
                    setEmkSummaryMode(mode);
                    if (mode === 'all') {
                      void runEmkAnalyze({ scopeMode: 'summary', summaryMode: 'all', scope: 'all' });
                    }
                  }}
                  selectedDepartments={emkSelectedDepartments}
                  onSelectedDepartmentsChange={setEmkSelectedDepartments}
                  disabled={busy}
                  onApply={() =>
                    void runEmkAnalyze({
                      scopeMode: 'summary',
                      summaryMode: emkSummaryMode,
                      scope: emkSummaryMode === 'all' ? 'all' : 'multi',
                      departments: emkSelectedDepartments,
                    })
                  }
                />
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
                  {emk.emk_variant_label && (
                    <span>
                      Тип: <strong>{emk.emk_variant_label}</strong>
                    </span>
                  )}
                  {emk.emk_variant === 'current' ? (
                    <label className="field emk-asof-field" title="Дата среза для расчёта койко-дней">
                      На дату
                      <span className="emk-asof-controls">
                        <input
                          type="date"
                          value={emkAsOf}
                          disabled={busy}
                          onChange={(e) => {
                            const next = e.target.value;
                            setEmkAsOf(next);
                            if (next) void runEmkAnalyze({ asOf: next });
                          }}
                        />
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={busy || emkAsOf === todayIso()}
                          title="Поставить сегодняшнюю дату и пересчитать"
                          onClick={() => {
                            const next = todayIso();
                            setEmkAsOf(next);
                            void runEmkAnalyze({ asOf: next });
                          }}
                        >
                          Сегодня
                        </button>
                      </span>
                    </label>
                  ) : (
                    <span>
                      Период:{' '}
                      <strong>
                        {emk.period_start || emk.period_end
                          ? `${fmtDateRu(emk.period_start)} — ${fmtDateRu(emk.period_end)}`
                          : 'не определён'}
                      </strong>
                    </span>
                  )}
                  {emk.department && (
                    <span>
                      Отделение: <strong>{emk.department}</strong>
                    </span>
                  )}
                </div>
                {emk.emk_variant === 'current' && (
                  <div className="info-banner emk-current-info">
                    <div className="emk-current-info__title">
                      Что анализируется в отчёте «Текущие пациенты»
                    </div>
                    <ul>
                      <li>
                        Учитывается <strong>один пациент = один КВС</strong> (последнее движение;
                        приёмное + коечное не дублируются).
                      </li>
                      <li>
                        Койко-дни считаются от <strong>даты поступления</strong> до даты среза{' '}
                        <strong>{fmtDateRu(emk.as_of || emk.period_end)}</strong>
                        {emk.as_of && emkAsOf && isoFromEmkDate(emk.as_of) !== emkAsOf
                          ? ' (идёт пересчёт…)'
                          : ''}
                        .
                      </li>
                      <li>
                        Проверки <strong>эпикриза, МКСБ, ИДС и ЭМД</strong> не выполняются —
                        пациенты ещё не выписаны.
                      </li>
                      <li>
                        <strong>Первичный осмотр</strong> в приёмном отделении не считается
                        нарушением; в коечных отделениях — считается.
                      </li>
                      <li>
                        СКП и длительная госпитализация считаются по порогам из настроек.
                      </li>
                    </ul>
                  </div>
                )}
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
                      ['share', 'Структура', 'section_share', 'Доли типов нарушений'],
                      ['age', 'Возраст', 'section_age', 'Распределение пациентов по возрасту'],
                      ['violations', 'Нарушения', 'section_violations', 'Таблица нарушений по историям'],
                      ['doctors', 'Врачи', 'section_doctors', 'Сводка по лечащим врачам'],
                      ['skp', 'СКП', 'section_skp', 'Случаи краткосрочного пребывания'],
                    ] as const
                  )
                    .filter(([, , key]) => emkShow(key))
                    .map(([id, label, , tip]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${emkSub === id ? 'active' : ''}`}
                      title={tip}
                      onClick={() => setEmkSub(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {emk.snils_available && (
                  <label className="emk-snils-split" title="Развести показатели по наличию СНИЛС">
                    <input
                      type="checkbox"
                      checked={emkSplitSnils}
                      onChange={(e) => setEmkSplitSnils(e.target.checked)}
                    />
                    Разделить с СНИЛС / без СНИЛС
                  </label>
                )}

                <div className="panel">
                  {emkSub === 'share' && (
                    <>
                      <div className="charts-row">
                        <div className="chart-block">
                          <h4>Структура нарушений, %</h4>
                          <BarChart
                            items={shareBars}
                            unit="%"
                            itemHint="Двойной клик — список нарушений этого типа"
                            onItemDoubleClick={(item) => openViolationType(item.label)}
                          />
                        </div>
                        {(snilsSplitOn ? coverageGroups.length > 0 : coverageBars.length > 0) && (
                          <div className="chart-block chart-block--below">
                            <h4>
                              Истории с / без нарушений
                              {snilsSplitOn ? ' (по СНИЛС)' : ''}
                            </h4>
                            {snilsSplitOn ? (
                              <BarChart
                                groups={coverageGroups}
                                legend={[
                                  { key: 'with', label: 'с СНИЛС', color: 'var(--danger)' },
                                  { key: 'without', label: 'без СНИЛС', color: '#c45c5c' },
                                ]}
                                seriesHint="Двойной клик — список историй этой группы"
                                onSeriesDoubleClick={(group, series) => {
                                  const snilsPart =
                                    series.key === 'without' ? 'без СНИЛС' : 'с СНИЛС';
                                  const key =
                                    group.label === 'Без нарушений'
                                      ? series.key === 'without'
                                        ? 'without_violations_no_snils'
                                        : 'without_violations_snils'
                                      : series.key === 'without'
                                        ? 'with_violations_no_snils'
                                        : 'with_violations_snils';
                                  openCoverageList(`${group.label} · ${snilsPart}`, key);
                                }}
                              />
                            ) : (
                              <BarChart
                                items={coverageBars}
                                itemHint="Двойной клик — список историй"
                                onItemDoubleClick={(item) => {
                                  const key =
                                    item.label === 'Без нарушений'
                                      ? 'without_violations'
                                      : 'with_violations';
                                  openCoverageList(item.label, key);
                                }}
                              />
                            )}
                          </div>
                        )}
                      </div>
                      <DataTable rows={shareTableRows} />
                      {snilsSplitOn && coverageTableRows.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <h4>Истории с / без нарушений</h4>
                          <DataTable rows={coverageTableRows} />
                        </div>
                      )}
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
                  {emkSub === 'violations' && (
                    <DataTable
                      rows={emk.violations}
                      initialQuery={violTableFilter}
                      queryResetKey={violTableFilterKey}
                      filterPlaceholder="Поиск / тип нарушения…"
                    />
                  )}
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
              <button
                className="btn btn-primary"
                type="button"
                disabled={busy}
                title="Загрузить один или несколько месячных отчётов КСГ"
                onClick={loadKsg}
              >
                Загрузить КСГ
              </button>
              <span className="muted toolbar-profile" title="Активный профиль формата КСГ">
                {activeProfileLabel(config, 'ksg')}
              </span>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksgFiles.length}
                title="Удалить активный файл КСГ из списка"
                onClick={() => void removeKsg()}
              >
                Удалить
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksgFiles.length}
                title="Пересчитать анализ с текущими фильтрами"
                onClick={() => void runKsgAnalyze()}
              >
                Пересчитать
              </button>
              {ksgPeriods.length > 0 && (
                <label className="toolbar-field">
                  <span className="muted">Период</span>
                  <select
                    value={ksgPeriod}
                    disabled={busy}
                    onChange={(e) => {
                      const value = e.target.value;
                      setKsgPeriod(value);
                      void runKsgAnalyze({ period: value });
                    }}
                  >
                    <option value="all">Весь период</option>
                    {ksgPeriods.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {ksgHasOther && (
                <div className="subtabs sub-tabs-inline">
                  {(
                    [
                      ['ksg', 'КСГ'],
                      ['other', 'Др. услуги'],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${ksgSource === id ? 'active' : ''}`}
                      disabled={busy}
                      onClick={() => {
                        setKsgSource(id);
                        void runKsgAnalyze({ source: id });
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
              {ksgDepartments.length > 0 && (
                <EmkDepartmentScope
                  radioName="ksg-summary-mode"
                  departments={ksgDepartments}
                  singleDepartment={ksgDepartment}
                  onSingleDepartmentChange={(value) => {
                    setKsgDepartment(value);
                    void runKsgAnalyze({ scopeMode: 'single', department: value, scope: 'single' });
                  }}
                  scopeMode={ksgScopeMode}
                  onScopeModeChange={(mode) => {
                    setKsgScopeMode(mode);
                    if (mode === 'single') {
                      if (ksgCompareMode === 'departments') {
                        setKsgCompareMode('months');
                        setCompare(null);
                      }
                      if (ksgDepartment) {
                        void runKsgAnalyze({ scopeMode: 'single', department: ksgDepartment, scope: 'single' });
                      }
                    } else {
                      void runKsgAnalyze({
                        scopeMode: 'summary',
                        summaryMode: ksgSummaryMode,
                        scope: ksgSummaryMode === 'all' ? 'all' : 'multi',
                        departments: ksgSelectedDepartments,
                      });
                    }
                  }}
                  summaryMode={ksgSummaryMode}
                  onSummaryModeChange={(mode) => {
                    setKsgSummaryMode(mode);
                    if (mode === 'all') {
                      void runKsgAnalyze({ scopeMode: 'summary', summaryMode: 'all', scope: 'all' });
                    }
                  }}
                  selectedDepartments={ksgSelectedDepartments}
                  onSelectedDepartmentsChange={setKsgSelectedDepartments}
                  disabled={busy}
                  onApply={() =>
                    void runKsgAnalyze({
                      scopeMode: 'summary',
                      summaryMode: ksgSummaryMode,
                      scope: ksgSummaryMode === 'all' ? 'all' : 'multi',
                      departments: ksgSelectedDepartments,
                    })
                  }
                />
              )}
              <label className="toolbar-field">
                <span className="muted">Сравнение</span>
                <select
                  value={ksgCompareMode}
                  disabled={busy}
                  onChange={(e) => {
                    setKsgCompareMode(e.target.value as 'months' | 'departments');
                    setCompare(null);
                  }}
                >
                  <option value="months">Месяцы / файлы</option>
                  {ksgScopeMode === 'summary' && (
                    <option value="departments">Отделения</option>
                  )}
                </select>
              </label>
              <button
                className="btn"
                type="button"
                disabled={
                  busy
                  || (ksgCompareMode === 'months'
                    ? compareIndices.length < 2
                    : ksgScopeMode !== 'summary' || ksgCompareDepartments.length < 2)
                }
                title={
                  ksgCompareMode === 'months'
                    ? 'Сравнить отмеченные месяцы (≥ 2 файла)'
                    : 'Сравнить отделения в текущем файле (≥ 2)'
                }
                onClick={() => void runCompare()}
              >
                {ksgCompareMode === 'months' ? 'Сравнить месяцы' : 'Сравнить отделения'}
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksg}
                title="Сохранить результаты анализа КСГ в файл"
                onClick={() => setExportOpen(true)}
              >
                Сохранить…
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ksg}
                title="Скопировать краткую сводку КСГ в буфер обмена"
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
                    title={`Открыть анализ: ${f.label || f.name}`}
                    onClick={() => void selectKsg(i)}
                  >
                    {f.label || f.name}
                  </button>
                ))}
              </div>
            )}

            {ksgCompareMode === 'months' && ksgFiles.length >= 2 && (
              <div className="compare-pick">
                <span className="muted">Сравнивать:</span>
                {ksgFiles.map((f, i) => {
                  const on = compareIndices.includes(i);
                  return (
                    <label
                      key={f.path}
                      className="compare-pick__item"
                      title={
                        on
                          ? `Убрать «${f.label || f.name}» из сравнения`
                          : `Добавить «${f.label || f.name}» к сравнению`
                      }
                    >
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

            {ksgScopeMode === 'summary'
              && ksgCompareMode === 'departments'
              && ksgDepartments.length >= 2 && (
              <div className="compare-pick">
                <div className="compare-pick__head">
                  <span className="muted">Отделения:</span>
                  <span className="muted compare-pick__count">
                    Отмечено: {ksgCompareDepartments.length} из {ksgDepartments.length}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost compare-pick__action"
                    disabled={busy || ksgCompareDepartments.length === ksgDepartments.length}
                    title="Отметить все отделения для сравнения"
                    onClick={() => {
                      setKsgCompareDepartments([...ksgDepartments]);
                      setCompare(null);
                    }}
                  >
                    Выбрать все
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost compare-pick__action"
                    disabled={busy || ksgCompareDepartments.length === 0}
                    title="Снять отметку со всех отделений"
                    onClick={() => {
                      setKsgCompareDepartments([]);
                      setCompare(null);
                    }}
                  >
                    Снять все
                  </button>
                </div>
                <div className="compare-pick__list">
                {ksgDepartments.map((dep) => {
                  const on = ksgCompareDepartments.includes(dep);
                  return (
                    <label key={dep} className="compare-pick__item" title={dep}>
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={busy}
                        onChange={() => {
                          setKsgCompareDepartments((prev) => {
                            if (prev.includes(dep)) return prev.filter((x) => x !== dep);
                            return [...prev, dep];
                          });
                          setCompare(null);
                        }}
                      />
                      {dep.length > 36 ? `${dep.slice(0, 33)}…` : dep}
                    </label>
                  );
                })}
                </div>
              </div>
            )}

            {!ksg ? (
              <div className="empty">
                <h2>Анализ КСГ</h2>
                <p>Загрузите общий реестр стационара или помесячный отчёт КСГ.</p>
              </div>
            ) : (
              <>
                {(ksg.department || ksg.period_label) && (
                  <p className="muted scope-hint">
                    {ksg.department ? <>Отделение: <strong>{ksg.department}</strong></> : null}
                    {ksg.period_label ? <> · Период: <strong>{ksg.period_label}</strong></> : null}
                    {ksg.source === 'other' ? <> · <strong>Др. услуги</strong></> : null}
                  </p>
                )}
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
                  {ksg.policy_check_enabled && ksgShow('kpi_policy_smo') && (
                    <Kpi title="Полис / СМО" value={fmtNum(ksg.policy_issues?.length ?? ksg.total_policy_issues)} />
                  )}
                </div>

                <div className="subtabs">
                  {(
                    [
                      ['doctors', 'Суммы по врачам', 'section_doctors', 'Суммы оплаты по врачам'],
                      ['cases', 'Случаи', 'section_cases', 'Дешёвые, дорогие случаи, КСЛП и полис/СМО'],
                      ['ops', 'Операции', 'section_ops', 'Сводка операций в отчёте КСГ'],
                      ['departments', 'По отделениям', 'section_departments', 'KPI по отделениям стационара'],
                      ['compare', 'Сравнение', 'section_compare', 'Сравнение месяцев или отделений'],
                    ] as const
                  )
                    .filter(([, , key]) => ksgShow(key))
                    .map(([id, label, , tip]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${ksgSub === id ? 'active' : ''}`}
                      title={tip}
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
                      <DataTable
                        rows={ksgCaseRows(ksg.low_money)}
                        columnOrder={KSG_CASE_COLUMN_ORDER}
                        sortColumn="Сумма к оплате"
                      />
                      <h3 style={{ marginTop: 16 }}>Дорогие случаи</h3>
                      <DataTable
                        rows={ksgCaseRows(ksg.high_money)}
                        columnOrder={KSG_CASE_COLUMN_ORDER}
                        sortColumn="Сумма к оплате"
                      />
                      <h3 style={{ marginTop: 16 }}>КСЛП</h3>
                      <DataTable rows={ksg.kslp_issues || []} />
                      {ksg.policy_check_enabled && (
                        <>
                          <h3 style={{ marginTop: 16 }}>Полис / СМО</h3>
                          <DataTable rows={ksg.policy_issues || []} />
                        </>
                      )}
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
                  {ksgSub === 'departments' && (
                    <>
                      <BarChart
                        items={(ksg.by_department || []).map((row) => ({
                          label: String(row['Отделение'] ?? ''),
                          value: Number(row['Сумма'] ?? 0),
                        }))}
                      />
                      <div style={{ marginTop: 12 }}>
                        <DataTable rows={ksg.by_department || []} />
                      </div>
                    </>
                  )}
                  {ksgSub === 'compare'
                    && (compare ? (
                      <KsgComparePanel
                        compare={compare}
                        chartsOn={compareCharts}
                        onChartsChange={setCompareCharts}
                      />
                    ) : (
                      <div className="muted">
                        {ksgCompareMode === 'months'
                          ? 'Отметьте месяцы выше и нажмите «Сравнить месяцы» (нужно ≥ 2).'
                          : 'Отметьте отделения и нажмите «Сравнить отделения» (нужно ≥ 2).'}
                      </div>
                    ))}
                </div>
              </>
            )}
          </>
        )}

        {tab === 'ops' && (
          <>
            <div className="toolbar">
              <button
                className="btn btn-primary"
                type="button"
                disabled={busy}
                title="Загрузить отчёт по выполненным операциям и операционным столам"
                onClick={loadOps}
              >
                Загрузить Excel
              </button>
              <span className="muted toolbar-profile" title="Активный профиль формата операций">
                {activeProfileLabel(config, 'ops')}
              </span>
              <button
                className="btn"
                type="button"
                disabled={busy || !ops}
                title="Сохранить результаты проверок операций в файл"
                onClick={() => setExportOpen(true)}
              >
                Сохранить…
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ops}
                title="Скопировать краткую сводку по операциям в буфер обмена"
                onClick={() => void copySummary()}
              >
                {copyFlash && tab === 'ops' ? 'Скопировано' : 'Копировать сводку'}
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !ops}
                title="Распечатать таблицы длительных операций и операций без опер.стола"
                onClick={() => setOpsPrintOpen(true)}
              >
                Печать таблиц
              </button>
              <button
                className="btn"
                type="button"
                disabled={busy || !opsFile}
                title="Пересчитать проверки с текущими настройками и отделением"
                onClick={() => void reanalyzeOps()}
              >
                Пересчитать
              </button>
              {opsDepartments.length > 0 && (
                <EmkDepartmentScope
                  radioName="ops-summary-mode"
                  departments={opsDepartments}
                  singleDepartment={opsDepartment}
                  onSingleDepartmentChange={(value) => void reanalyzeOps(value)}
                  scopeMode={opsScopeMode}
                  onScopeModeChange={(mode) => {
                    setOpsScopeMode(mode);
                    if (mode === 'summary') {
                      if (opsSummaryMode === 'all') {
                        void runOpsAnalyze({
                          scopeMode: 'summary',
                          summaryMode: 'all',
                          scope: 'all',
                        });
                      } else if (opsSelectedDepartments.length) {
                        void runOpsAnalyze({
                          scopeMode: 'summary',
                          summaryMode: 'multi',
                          scope: 'multi',
                          departments: opsSelectedDepartments,
                        });
                      }
                    } else if (opsDepartment) {
                      void reanalyzeOps(opsDepartment);
                    }
                  }}
                  summaryMode={opsSummaryMode}
                  onSummaryModeChange={(mode) => {
                    setOpsSummaryMode(mode);
                    if (mode === 'all') {
                      void runOpsAnalyze({
                        scopeMode: 'summary',
                        summaryMode: 'all',
                        scope: 'all',
                      });
                    }
                  }}
                  selectedDepartments={opsSelectedDepartments}
                  onSelectedDepartmentsChange={setOpsSelectedDepartments}
                  disabled={busy}
                  onApply={() =>
                    void runOpsAnalyze({
                      scopeMode: 'summary',
                      summaryMode: opsSummaryMode,
                      scope: opsSummaryMode === 'all' ? 'all' : 'multi',
                      departments: opsSelectedDepartments,
                    })
                  }
                />
              )}
            </div>

            {!ops ? (
              <div
                className={`empty${dragOver ? ' drag-over' : ''}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => void onDropFiles(e)}
              >
                <h2>Проверки операций</h2>
                <p>
                  Загрузите «Отчёт по выполненным операциям и операционным столам» или перетащите
                  файл сюда.
                </p>
              </div>
            ) : (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  {ops.file_name || opsFile}
                  {(ops.department || opsDepartment) && ` · ${ops.department || opsDepartment}`}
                  {' · '}
                  порог длительности &gt; {ops.long_op_hours} ч
                </p>
                <div className="kpi-grid">
                  <Kpi title="Всего операций" value={fmtNum(ops.total_ops)} />
                  <Kpi title={`Длительные (>${ops.long_op_hours} ч)`} value={fmtNum(ops.long_count)} />
                  <Kpi title="Без опер.стола" value={fmtNum(ops.missing_table_count)} />
                </div>
                {opsScopeMode === 'summary' && (ops.violations_summary?.length ?? 0) > 0 && (
                  <div className="panel" style={{ marginBottom: 12 }}>
                    <h4 style={{ marginTop: 0 }}>Сводка по нарушениям</h4>
                    <DataTable rows={ops.violations_summary || []} />
                  </div>
                )}
                <div className="subtabs">
                  {(
                    [
                      ['long', `Длительные (${ops.long_count})`, 'Операции дольше порога длительности'],
                      ['table', `Без опер.стола (${ops.missing_table_count})`, 'Операции без указания операционного стола'],
                    ] as const
                  ).map(([id, label, tip]) => (
                    <button
                      key={id}
                      type="button"
                      className={`chip ${opsSub === id ? 'active' : ''}`}
                      title={tip}
                      onClick={() => setOpsSub(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="panel">
                  {opsSub === 'long' && (
                    <DataTable rows={ops.long_ops} formatCopy={opsRowsToCompactCopy} />
                  )}
                  {opsSub === 'table' && (
                    <DataTable rows={ops.missing_table} formatCopy={opsRowsToCompactCopy} />
                  )}
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
            if (emkFile) {
              if (emkScopeMode === 'summary') {
                await runEmkAnalyze();
              } else {
                await reanalyzeEmk(department);
              }
            }
            if (ksgFiles.length) await reanalyzeKsg();
            if (opsFile) await reanalyzeOps();
          }}
        />
      )}

      {violOpen && emk?.violations_summary && (
        <ViolationsSummaryDialog
          sections={emk.violations_summary}
          onClose={() => setViolOpen(false)}
        />
      )}

      {violTypeOpen && (
        <ViolationTypeDialog
          typeLabel={violTypeOpen}
          rows={violTypeRows}
          onClose={() => setViolTypeOpen(null)}
          onOpenInTable={() => openViolationTypeInTable(violTypeOpen)}
        />
      )}

      {coverageListOpen && (
        <ViolationTypeDialog
          typeLabel={coverageListOpen.title}
          rows={coverageListRows}
          showOpenInTable={false}
          onClose={() => setCoverageListOpen(null)}
        />
      )}

      {exportOpen && (
        <ExportDialog
          kind={tab === 'emk' ? 'emk' : tab === 'ops' ? 'ops' : 'ksg'}
          defaultName={
            tab === 'emk'
              ? emk?.report_basename || 'Отчет ЭМК'
              : tab === 'ops'
                ? 'Проверки_операций'
                : `Отчет_КСГ_${ksgFiles[ksgActive]?.label || 'файл'}`
          }
          onClose={() => setExportOpen(false)}
          onExport={doExport}
        />
      )}

      {opsPrintOpen && ops && (
        <OpsPrintDialog
          payload={{
            fileName: ops.file_name || opsFile || '—',
            department: ops.department,
            scope: ops.scope,
            departmentsInScope: ops.departments_in_scope,
            longOpHours: ops.long_op_hours,
            longOps: ops.long_ops,
            missingTable: ops.missing_table,
          }}
          onClose={() => setOpsPrintOpen(false)}
          onPrinted={() => setStatus('Отправлено на печать')}
          onError={(message) => setError(message)}
        />
      )}

      {aboutOpen && (
        <Modal title="О программе" onClose={() => setAboutOpen(false)}>
          <div className="about-body">
            <p>
              <strong>Анализ работы отделения</strong>
            </p>
            <p>ЭМК, КСГ и операции: отчёты, нарушения, сравнение месяцев.</p>
            <p>Версия {version}</p>
            <p className="muted">
              Горячие клавиши: ⌘/Ctrl+O — открыть, ⌘/Ctrl+S — сохранить,
              <br />
              ⌘/Ctrl+C — копировать выделенное, ⌘/Ctrl+Shift+C — сводку.
            </p>
          </div>
        </Modal>
      )}

      {whatsNewOpen && (
        <Modal title="Что нового" wide onClose={() => setWhatsNewOpen(false)}>
          <div className="changelog">
            {changelog.map((entry) => (
              <section key={entry.version} className="changelog__entry">
                <h3>{entry.title || `Версия ${entry.version}`}</h3>
                <ul>
                  {(entry.items || []).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            ))}
            {!changelog.length && <p className="muted">Нет записей в журнале изменений.</p>}
          </div>
        </Modal>
      )}
    </div>
  );
}
