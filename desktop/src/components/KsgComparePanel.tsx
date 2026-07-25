import { useEffect, useMemo, useState } from 'react';
import { BarChart } from './BarChart';
import { DataTable } from './DataTable';

export type CompareResult = {
  labels: string[];
  total_patients: number[];
  total_sum: number[];
  avg_kz: number[];
  kslp_issues: number[];
  doctors?: string[];
  doctor_sums?: Record<string, number[]>;
};

export type ChartId = 'patients' | 'sum' | 'kz' | 'kslp';

export type CompareChartsState = Record<ChartId, boolean>;

export const DEFAULT_COMPARE_CHARTS: CompareChartsState = {
  patients: true,
  sum: true,
  kz: true,
  kslp: true,
};

const CHARTS: { id: ChartId; label: string; color?: string }[] = [
  { id: 'patients', label: 'Пациенты' },
  { id: 'sum', label: 'Сумма', color: 'var(--ok)' },
  { id: 'kz', label: 'Средний КЗ', color: 'var(--warning)' },
  { id: 'kslp', label: 'Нарушения КСЛП', color: 'var(--danger)' },
];

/** Drop vs previous month ≥ 15% */
const DROP_RATIO = 0.85;
/** Rise vs previous month ≥ 20% */
const RISE_RATIO = 1.2;

function fmtNum(value: unknown, digits = 0): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('ru-RU', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function mean(nums: number[]): number {
  if (!nums.length) return 0;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function momClass(
  kind: 'patients' | 'sum' | 'kz' | 'kslp',
  prev: number,
  cur: number,
): string | undefined {
  if (!(prev > 0) || !Number.isFinite(cur) || !Number.isFinite(prev)) return undefined;
  if (kind === 'patients' && cur < prev * DROP_RATIO) return 'cell-anomaly-down';
  if (kind === 'sum' && cur > prev * RISE_RATIO) return 'cell-anomaly-up';
  if (kind === 'kslp' && cur > prev * RISE_RATIO) return 'cell-anomaly-up';
  if (kind === 'kz' && (cur > prev * RISE_RATIO || cur < prev * DROP_RATIO)) {
    return cur > prev ? 'cell-anomaly-up' : 'cell-anomaly-down';
  }
  return undefined;
}

export function KsgComparePanel({
  compare,
  chartsOn: chartsControlled,
  onChartsChange,
}: {
  compare: CompareResult;
  chartsOn?: CompareChartsState;
  onChartsChange?: (next: CompareChartsState) => void;
}) {
  const [localCharts, setLocalCharts] = useState<CompareChartsState>(
    chartsControlled || DEFAULT_COMPARE_CHARTS,
  );

  useEffect(() => {
    if (chartsControlled) setLocalCharts(chartsControlled);
  }, [chartsControlled]);

  const chartsOn = chartsControlled || localCharts;

  const setCharts = (next: CompareChartsState) => {
    if (!chartsControlled) setLocalCharts(next);
    onChartsChange?.(next);
  };

  const labels = compare.labels || [];

  const { totalsRows, totalsMeta } = useMemo(() => {
    const patients = compare.total_patients || [];
    const sums = compare.total_sum || [];
    const kz = compare.avg_kz || [];
    const kslp = compare.kslp_issues || [];

    const mk = (
      title: string,
      kind: ChartId,
      values: number[],
      digits: number,
      totalMode: 'sum' | 'mean',
    ) => {
      const row: Record<string, unknown> = { Показатель: title };
      labels.forEach((label, i) => {
        row[label] = fmtNum(values[i] ?? 0, digits);
      });
      const total =
        totalMode === 'mean'
          ? mean(values.map((v) => Number(v) || 0))
          : values.reduce((a, b) => a + (Number(b) || 0), 0);
      row['Итого'] = fmtNum(total, digits);
      return { row, kind, values };
    };

    const meta = [
      mk('Количество пациентов', 'patients', patients, 0, 'sum'),
      mk('Общая сумма, ₽', 'sum', sums, 0, 'sum'),
      mk('Средний КЗ', 'kz', kz, 3, 'mean'),
      mk('Нарушений КСЛП', 'kslp', kslp, 0, 'sum'),
    ];
    return { totalsRows: meta.map((m) => m.row), totalsMeta: meta };
  }, [compare, labels]);

  const doctorRows = useMemo(() => {
    const doctors = compare.doctors || [];
    const sums = compare.doctor_sums || {};
    return doctors.map((doc) => {
      const series = sums[doc] || [];
      const row: Record<string, unknown> = { Врач: doc };
      let total = 0;
      labels.forEach((label, i) => {
        const v = Number(series[i] || 0);
        total += v;
        row[label] = fmtNum(v, 0);
      });
      row['Итого'] = fmtNum(total, 0);
      return row;
    });
  }, [compare, labels]);

  const seriesFor = (id: ChartId): number[] => {
    switch (id) {
      case 'patients':
        return compare.total_patients || [];
      case 'sum':
        return compare.total_sum || [];
      case 'kz':
        return compare.avg_kz || [];
      case 'kslp':
        return compare.kslp_issues || [];
    }
  };

  const toggle = (id: ChartId) => {
    setCharts({ ...chartsOn, [id]: !chartsOn[id] });
  };

  const totalsCellClass = (
    row: Record<string, unknown>,
    col: string,
    rowIndex: number,
  ): string | undefined => {
    if (col === 'Показатель' || col === 'Итого') return undefined;
    const meta = totalsMeta[rowIndex];
    if (!meta) return undefined;
    const mi = labels.indexOf(col);
    if (mi <= 0) return undefined;
    const prev = Number(meta.values[mi - 1] || 0);
    const cur = Number(meta.values[mi] || 0);
    return momClass(meta.kind, prev, cur);
  };

  return (
    <div className="ksg-compare">
      <h3>Общие показатели (накопление)</h3>
      <p className="muted" style={{ margin: '0 0 8px' }}>
        Подсветка: падение пациентов ≥15% или рост суммы / КСЛП / КЗ ≥20% к предыдущему месяцу.
      </p>
      <DataTable
        rows={totalsRows}
        filterable={false}
        getCellClass={totalsCellClass}
      />

      {doctorRows.length > 0 && (
        <>
          <h3 style={{ marginTop: 16 }}>Суммы к оплате по врачам (накопление)</h3>
          <DataTable
            rows={doctorRows}
            filterPlaceholder="Поиск врача…"
          />
        </>
      )}

      <h3 style={{ marginTop: 16 }}>Графики</h3>
      <div className="compare-chart-toggles">
        {CHARTS.map((c) => (
          <label key={c.id} className="compare-chart-toggle">
            <input
              type="checkbox"
              checked={chartsOn[c.id]}
              onChange={() => toggle(c.id)}
            />
            {c.label}
          </label>
        ))}
      </div>

      {CHARTS.filter((c) => chartsOn[c.id]).map((c) => (
        <div key={c.id} style={{ marginTop: 12 }}>
          <h4 className="compare-chart-title">{c.label}</h4>
          <BarChart
            items={labels.map((label, i) => ({
              label,
              value: Number(seriesFor(c.id)[i] || 0),
              color: c.color,
            }))}
          />
        </div>
      ))}

      {!CHARTS.some((c) => chartsOn[c.id]) && (
        <p className="muted" style={{ marginTop: 8 }}>
          Включите хотя бы один показатель, чтобы показать графики.
        </p>
      )}
    </div>
  );
}
