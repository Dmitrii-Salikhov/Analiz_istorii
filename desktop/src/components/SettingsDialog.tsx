import { useEffect, useMemo, useState } from 'react';
import { Modal } from './Modal';
import {
  SearchableMultiSelect,
  SearchableSingleSelect,
  type OpItem,
} from './SearchableSelect';

export type DisplayMap = Record<string, boolean>;

export type KslpRule = {
  id: string;
  name?: string;
  codes: string[];
};

export type ReportProfile = {
  id: string;
  name?: string;
  header_fragments?: string[];
  required_columns?: string[];
  aliases?: Record<string, string[]>;
};

export type ReportProfilesConfig = {
  emk_active?: string;
  ksg_active?: string;
  emk?: Record<string, ReportProfile>;
  ksg?: Record<string, ReportProfile>;
};

export type AppConfig = {
  date_format?: string;
  theme?: string;
  ksg_threshold_low?: number;
  ksg_threshold_high?: number;
  kslp_age_min?: number;
  kslp_age_max?: number;
  kslp_senior_age?: number;
  long_stay_days?: number;
  kslp_operations_codes?: string[];
  kslp_rules?: KslpRule[];
  preferred_department?: string;
  known_departments?: string[];
  github_repo?: string;
  check_updates_on_start?: boolean;
  emk_display?: DisplayMap;
  ksg_display?: DisplayMap;
  last_main_tab?: number;
  ui_prefs?: {
    main_tab?: 'emk' | 'ksg';
    emk_sub?: string;
    ksg_sub?: string;
    compare_charts?: {
      patients?: boolean;
      sum?: boolean;
      kz?: boolean;
      kslp?: boolean;
    };
  };
  report_profiles?: ReportProfilesConfig;
};

const EMK_KPI: [string, string][] = [
  ['kpi_patients', 'KPI: пациенты'],
  ['kpi_avg_beddays', 'KPI: ср. койко-дни'],
  ['kpi_urgent', 'KPI: экстренные'],
  ['kpi_planned', 'KPI: плановые'],
  ['kpi_violations', 'KPI: нарушения'],
  ['kpi_skp', 'KPI: СКП'],
];

const EMK_SECTIONS: [string, string][] = [
  ['section_share', 'Раздел: структура нарушений'],
  ['section_age', 'Раздел: возраст'],
  ['section_violations', 'Раздел: нарушения (таблица)'],
  ['section_doctors', 'Раздел: врачи'],
  ['section_skp', 'Раздел: СКП'],
];

const KSG_KPI: [string, string][] = [
  ['kpi_patients', 'KPI: пациенты'],
  ['kpi_sum', 'KPI: сумма'],
  ['kpi_kz', 'KPI: средний КЗ'],
  ['kpi_no_service', 'KPI: без услуги'],
  ['kpi_kslp', 'KPI: КСЛП'],
];

const KSG_SECTIONS: [string, string][] = [
  ['section_doctors', 'Раздел: суммы по врачам'],
  ['section_cases', 'Раздел: случаи'],
  ['section_ops', 'Раздел: операции'],
  ['section_compare', 'Раздел: сравнение месяцев'],
];

type TabId = 'display' | 'levels' | 'kslp' | 'formats' | 'department' | 'system';

function codesKey(codes: string[]): string {
  return [...codes].map((c) => c.trim()).filter(Boolean).sort().join('|');
}

function normalizeRules(cfg: AppConfig): KslpRule[] {
  const raw = cfg.kslp_rules;
  if (Array.isArray(raw) && raw.length) {
    return raw
      .filter((r) => r && Array.isArray(r.codes) && r.codes.length)
      .map((r, i) => ({
        id: r.id || `rule-${i + 1}`,
        name: (r.name || `Правило ${i + 1}`).trim() || `Правило ${i + 1}`,
        codes: r.codes.map((c) => String(c).trim()).filter(Boolean),
      }));
  }
  const legacy = cfg.kslp_operations_codes || [];
  if (legacy.length) {
    return [{ id: 'migrated-ops', name: 'Правило 1', codes: [...legacy] }];
  }
  return [];
}

function newRuleId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `rule-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function SettingsDialog({
  initial,
  operations,
  departments,
  onClose,
  onSave,
}: {
  initial: AppConfig;
  operations: OpItem[];
  departments: string[];
  onClose: () => void;
  onSave: (cfg: AppConfig) => Promise<void>;
}) {
  const [cfg, setCfg] = useState<AppConfig>(() => ({
    ...initial,
    kslp_rules: normalizeRules(initial),
  }));
  const [tab, setTab] = useState<TabId>('display');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [githubUnlocked, setGithubUnlocked] = useState(false);
  const [draftCodes, setDraftCodes] = useState<string[]>([]);
  const [draftName, setDraftName] = useState('');
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formatKind, setFormatKind] = useState<'emk' | 'ksg'>('emk');

  const opLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const op of operations) {
      map.set(op.code, op.name || op.code);
    }
    return map;
  }, [operations]);

  useEffect(() => {
    setCfg({ ...initial, kslp_rules: normalizeRules(initial) });
    setGithubUnlocked(false);
    setDraftCodes([]);
    setDraftName('');
    setRuleError(null);
    setEditingId(null);
  }, [initial]);

  const set = <K extends keyof AppConfig>(key: K, value: AppConfig[K]) => {
    setCfg((prev) => ({ ...prev, [key]: value }));
  };

  const setDisplay = (scope: 'emk_display' | 'ksg_display', key: string, on: boolean) => {
    setCfg((prev) => ({
      ...prev,
      [scope]: { ...(prev[scope] || {}), [key]: on },
    }));
  };

  const unlockGithub = () => {
    const ok = window.confirm(
      'Репозиторий GitHub нужен только для обновлений приложения.\n\n'
        + 'Менять его обычно не требуется. Продолжить?',
    );
    if (ok) setGithubUnlocked(true);
  };

  const startEditRule = (rule: KslpRule) => {
    setEditingId(rule.id);
    setDraftCodes([...rule.codes]);
    setDraftName(rule.name || '');
    setRuleError(null);
  };

  const cancelEditRule = () => {
    setEditingId(null);
    setDraftCodes([]);
    setDraftName('');
    setRuleError(null);
  };

  const saveRule = () => {
    const codes = draftCodes.map((c) => c.trim()).filter(Boolean);
    if (!codes.length) {
      setRuleError('Выберите хотя бы одну операцию.');
      return;
    }
    const key = codesKey(codes);
    const existing = cfg.kslp_rules || [];
    if (
      existing.some(
        (r) => codesKey(r.codes) === key && r.id !== editingId,
      )
    ) {
      setRuleError('Такое правило уже есть (тот же набор кодов).');
      return;
    }

    let next: KslpRule[];
    if (editingId) {
      const name = draftName.trim()
        || existing.find((r) => r.id === editingId)?.name
        || 'Правило';
      next = existing.map((r) =>
        (r.id === editingId ? { ...r, name, codes } : r),
      );
    } else {
      const name = draftName.trim() || `Правило ${existing.length + 1}`;
      next = [...existing, { id: newRuleId(), name, codes }];
    }
    setCfg((prev) => ({
      ...prev,
      kslp_rules: next,
      kslp_operations_codes: next[0]?.codes || [],
    }));
    cancelEditRule();
  };

  const removeRule = (id: string) => {
    if (editingId === id) cancelEditRule();
    setCfg((prev) => {
      const next = (prev.kslp_rules || []).filter((r) => r.id !== id);
      return {
        ...prev,
        kslp_rules: next,
        kslp_operations_codes: next[0]?.codes || [],
      };
    });
  };

  return (
    <Modal
      title="Настройки"
      wide
      onClose={onClose}
      hint="Пороги и КСЛП применяются после пересчёта / повторного анализа."
    >
      <div className="subtabs" style={{ marginBottom: 14 }}>
        {(
          [
            ['display', 'Отображение'],
            ['levels', 'Пороги'],
            ['kslp', 'КСЛП'],
            ['formats', 'Форматы'],
            ['department', 'Отделение'],
            ['system', 'Система'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`chip ${tab === id ? 'active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'display' && (
        <div className="form-grid">
          <div className="form-row">
            <label>ЭМК — что показывать</label>
            <div className="check-list">
              {[...EMK_KPI, ...EMK_SECTIONS].map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={cfg.emk_display?.[key] !== false}
                    onChange={(e) => setDisplay('emk_display', key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
          <div className="form-row">
            <label>КСГ — что показывать</label>
            <div className="check-list">
              {[...KSG_KPI, ...KSG_SECTIONS].map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={cfg.ksg_display?.[key] !== false}
                    onChange={(e) => setDisplay('ksg_display', key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'levels' && (
        <div className="form-grid">
          <div className="form-row">
            <label>Длительная госпитализация — порог койко-дней (&gt;)</label>
            <input
              type="number"
              min={1}
              value={String(cfg.long_stay_days ?? 7)}
              onChange={(e) => set('long_stay_days', Math.max(1, Number(e.target.value) || 7))}
            />
          </div>
          <div className="form-row">
            <label>Порог «дешёвых» КСГ (&lt;), ₽</label>
            <input
              value={String(cfg.ksg_threshold_low ?? 20000)}
              onChange={(e) => set('ksg_threshold_low', Number(e.target.value) || 0)}
            />
          </div>
          <div className="form-row">
            <label>Порог «дорогих» КСГ (&gt;), ₽</label>
            <input
              value={String(cfg.ksg_threshold_high ?? 100000)}
              onChange={(e) => set('ksg_threshold_high', Number(e.target.value) || 0)}
            />
          </div>
          <div className="form-row">
            <label>КСЛП возраст: от / до / старший ≥</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={String(cfg.kslp_age_min ?? 0)}
                onChange={(e) => set('kslp_age_min', Number(e.target.value) || 0)}
              />
              <input
                value={String(cfg.kslp_age_max ?? 4)}
                onChange={(e) => set('kslp_age_max', Number(e.target.value) || 0)}
              />
              <input
                value={String(cfg.kslp_senior_age ?? 75)}
                onChange={(e) => set('kslp_senior_age', Number(e.target.value) || 0)}
              />
            </div>
          </div>
          <div className="form-row">
            <label>Формат даты</label>
            <select
              value={cfg.date_format || 'dayfirst'}
              onChange={(e) => set('date_format', e.target.value)}
            >
              <option value="dayfirst">ДД.ММ.ГГГГ</option>
              <option value="monthfirst">ММ.ДД.ГГГГ</option>
            </select>
          </div>
        </div>
      )}

      {tab === 'kslp' && (
        <div className="form-grid">
          <p className="muted" style={{ margin: 0 }}>
            Комбинация операций → повышение КСЛП (должен быть &gt; 0). Срабатывает любое правило,
            если у пациента есть все коды из него.
          </p>

          <div className="form-row">
            <label>{editingId ? 'Редактирование правила — операции' : 'Новое правило — операции'}</label>
            <SearchableMultiSelect
              items={operations}
              value={draftCodes}
              onChange={(codes) => {
                setDraftCodes(codes);
                setRuleError(null);
              }}
            />
          </div>
          <div className="form-row">
            <label>Название правила (необязательно)</label>
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder={`Правило ${(cfg.kslp_rules || []).length + 1}`}
            />
          </div>
          <div className="kslp-rule-actions">
            <button
              className="btn btn-primary"
              type="button"
              disabled={!draftCodes.length}
              onClick={saveRule}
            >
              {editingId ? 'Сохранить правило' : 'Добавить правило'}
            </button>
            {editingId && (
              <button className="btn" type="button" onClick={cancelEditRule}>
                Отмена
              </button>
            )}
            <span className="muted">Эта комбинация даёт повышение КСЛП</span>
          </div>
          {ruleError && <div className="error-banner">{ruleError}</div>}

          <div className="form-row">
            <label>Сохранённые правила ({(cfg.kslp_rules || []).length})</label>
            {(cfg.kslp_rules || []).length === 0 ? (
              <p className="muted" style={{ margin: 0 }}>Пока нет правил — добавьте комбинацию выше.</p>
            ) : (
              <ul className="kslp-rules-list">
                {(cfg.kslp_rules || []).map((rule) => (
                  <li
                    key={rule.id}
                    className={`kslp-rule-card${editingId === rule.id ? ' kslp-rule-card--editing' : ''}`}
                  >
                    <div className="kslp-rule-card__head">
                      <strong>{rule.name || 'Правило'}</strong>
                      <div className="kslp-rule-card__btns">
                        <button
                          className="btn"
                          type="button"
                          onClick={() => startEditRule(rule)}
                        >
                          Изменить
                        </button>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => removeRule(rule.id)}
                        >
                          Удалить
                        </button>
                      </div>
                    </div>
                    <ul className="kslp-rule-codes">
                      {rule.codes.map((code) => (
                        <li key={code}>
                          <code>{code}</code>
                          {opLabel.get(code) ? (
                            <span className="muted"> — {opLabel.get(code)}</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {tab === 'formats' && (() => {
        const rp = cfg.report_profiles || {};
        const activeKey = formatKind === 'emk' ? 'emk_active' : 'ksg_active';
        const bucket = formatKind === 'emk' ? 'emk' : 'ksg';
        const activeId = (rp[activeKey] as string) || 'default';
        const profiles = (rp[bucket] as Record<string, ReportProfile>) || {};
        const profileIds = Object.keys(profiles).length
          ? Object.keys(profiles)
          : ['default'];
        const profile = profiles[activeId] || profiles.default || {
          id: activeId,
          name: activeId,
          aliases: {},
        };
        const aliases = profile.aliases || {};
        const aliasKeys = Object.keys(aliases).sort((a, b) => a.localeCompare(b, 'ru'));

        const patchProfiles = (next: ReportProfilesConfig) => {
          set('report_profiles', next);
        };

        const setActiveProfile = (id: string) => {
          patchProfiles({ ...rp, [activeKey]: id });
        };

        const setAliasText = (canon: string, text: string) => {
          const list = text
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean);
          const nextAliases = { ...aliases, [canon]: list.length ? list : [canon] };
          const nextProfile = { ...profile, id: profile.id || activeId, aliases: nextAliases };
          patchProfiles({
            ...rp,
            [bucket]: { ...profiles, [activeId]: nextProfile },
          });
        };

        const resetDefaults = () => {
          if (
            !window.confirm(
              'Сбросить профили форматов к стандартным? Пользовательские алиасы будут удалены.',
            )
          ) {
            return;
          }
          patchProfiles({
            emk_active: 'default',
            ksg_active: 'default',
            emk: {},
            ksg: {},
          });
        };

        return (
          <div className="form-grid">
            <div className="form-row inline" style={{ gap: 16 }}>
              <label className="inline">
                <input
                  type="radio"
                  checked={formatKind === 'emk'}
                  onChange={() => setFormatKind('emk')}
                />
                ЭМК
              </label>
              <label className="inline">
                <input
                  type="radio"
                  checked={formatKind === 'ksg'}
                  onChange={() => setFormatKind('ksg')}
                />
                КСГ
              </label>
            </div>
            <div className="form-row">
              <label>Активный профиль ({formatKind === 'emk' ? 'ЭМК' : 'КСГ'})</label>
              <select
                value={activeId}
                onChange={(e) => setActiveProfile(e.target.value)}
              >
                {profileIds.map((id) => (
                  <option key={id} value={id}>
                    {profiles[id]?.name || id}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label>
                Синонимы колонок — {profile.name || activeId}
              </label>
              <p className="muted" style={{ margin: '0 0 8px' }}>
                Каноническое имя → возможные заголовки в Excel (через запятую).
              </p>
              {aliasKeys.length === 0 ? (
                <p className="muted">Нет алиасов в профиле (после сохранения подставятся стандартные).</p>
              ) : (
                <div className="alias-table-wrap">
                  <table className="alias-table">
                    <thead>
                      <tr>
                        <th>Канон</th>
                        <th>Алиасы</th>
                      </tr>
                    </thead>
                    <tbody>
                      {aliasKeys.map((canon) => (
                        <tr key={canon}>
                          <td className="alias-table__canon">{canon}</td>
                          <td>
                            <input
                              value={(aliases[canon] || []).join(', ')}
                              onChange={(e) => setAliasText(canon, e.target.value)}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="form-row">
              <button className="btn" type="button" onClick={resetDefaults}>
                Сбросить к стандартным
              </button>
            </div>
          </div>
        );
      })()}

      {tab === 'department' && (
        <div className="form-grid">
          <div className="form-row">
            <label>Предпочитаемое отделение</label>
            <SearchableSingleSelect
              options={departments}
              value={cfg.preferred_department || ''}
              onChange={(v) => set('preferred_department', v)}
              placeholder="Начните вводить название отделения…"
            />
            <p className="muted" style={{ margin: 0 }}>
              Используется по умолчанию при загрузке отчёта ЭМК.
            </p>
          </div>
        </div>
      )}

      {tab === 'system' && (
        <div className="form-grid">
          <div className="form-row">
            <label>GitHub (owner/repo) — только для обновлений</label>
            {!githubUnlocked ? (
              <div className="github-lock">
                <code>{cfg.github_repo || '—'}</code>
                <button className="btn" type="button" onClick={unlockGithub}>
                  Изменить…
                </button>
                <p className="muted" style={{ margin: 0 }}>
                  Не меняйте, если не уверены: от этого зависит проверка обновлений.
                </p>
              </div>
            ) : (
              <input
                value={cfg.github_repo || ''}
                onChange={(e) => set('github_repo', e.target.value)}
              />
            )}
          </div>
          <label className="form-row inline">
            <input
              type="checkbox"
              checked={!!cfg.check_updates_on_start}
              onChange={(e) => set('check_updates_on_start', e.target.checked)}
            />
            Проверять обновления при запуске
          </label>
        </div>
      )}

      {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}

      <div className="modal__actions">
        <button className="btn" type="button" onClick={onClose}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              const rules = normalizeRules(cfg);
              await onSave({
                ...cfg,
                kslp_rules: rules,
                kslp_operations_codes: rules[0]?.codes || [],
              });
              onClose();
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить
        </button>
      </div>
    </Modal>
  );
}
