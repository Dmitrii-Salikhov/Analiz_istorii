export type SortMode = 'alpha' | 'asc' | 'desc';

export const SORT_MODE_HINTS: Record<SortMode, string> = {
  alpha: 'Сортировка по алфавиту (А→Я)',
  asc: 'Сортировка по возрастанию (меньше → больше)',
  desc: 'Сортировка по убыванию (больше → меньше)',
};

function parseSortableNumber(raw: unknown): number | null {
  const s = String(raw ?? '').trim().replace(/\s/g, '').replace(',', '.');
  if (!s || s === '—') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

const TEXT_COLUMN_HINTS =
  /врач|пациент|отделение|показатель|тип|нарушение|услуг|квс|талон|фио|замечание|операц/i;
const NUMERIC_COLUMN_HINTS =
  /сумма|колич|кз|кслп|возраст|итого|count|sum|total|пациенты|доля|%/i;

function numericColumnScore(rows: Record<string, unknown>[], col: string): number {
  let numeric = 0;
  let total = 0;
  for (const row of rows) {
    const v = row[col];
    if (v == null || v === '' || v === '—') continue;
    total++;
    if (parseSortableNumber(v) != null) numeric++;
  }
  if (!total) return 0;
  return numeric / total;
}

/** Колонка для сортировки: А→Я — текстовая, ↑/↓ — основная числовая. */
export function pickSortColumn(
  columns: string[],
  rows: Record<string, unknown>[],
  mode: SortMode,
): string {
  if (!columns.length) return '';
  if (mode === 'alpha') {
    const textCol = columns.find((c) => TEXT_COLUMN_HINTS.test(c));
    return textCol || columns[0];
  }

  let best = columns[columns.length - 1] || columns[0];
  let bestScore = -1;
  for (const col of columns) {
    const ratio = numericColumnScore(rows, col);
    let score = ratio;
    if (NUMERIC_COLUMN_HINTS.test(col)) score += 0.35;
    if (col === 'Итого') score += 0.2;
    if (TEXT_COLUMN_HINTS.test(col) && !NUMERIC_COLUMN_HINTS.test(col)) score -= 0.5;
    if (score > bestScore) {
      bestScore = score;
      best = col;
    }
  }
  if (bestScore >= 0.45) return best;

  const hinted = columns.find((c) => NUMERIC_COLUMN_HINTS.test(c));
  return hinted || columns[columns.length - 1] || columns[0];
}

/** Сравнение двух ячеек таблицы для выбранного режима. */
export function compareCellValues(a: unknown, b: unknown, mode: SortMode): number {
  const sa = String(a ?? '');
  const sb = String(b ?? '');

  if (mode === 'alpha') {
    return sa.localeCompare(sb, 'ru', { sensitivity: 'base', numeric: true });
  }

  const na = parseSortableNumber(a);
  const nb = parseSortableNumber(b);
  if (na != null && nb != null) {
    return mode === 'desc' ? nb - na : na - nb;
  }

  const cmp = sa.localeCompare(sb, 'ru', { numeric: true, sensitivity: 'base' });
  return mode === 'desc' ? -cmp : cmp;
}

export function sortRows<T extends Record<string, unknown>>(
  rows: T[],
  column: string,
  mode: SortMode,
): T[] {
  if (!rows.length || !column) return rows;
  return [...rows].sort((a, b) => compareCellValues(a[column], b[column], mode));
}

export function sortBarItems<T extends { label: string; value: number }>(
  items: T[],
  mode: SortMode,
): T[] {
  if (!items.length) return items;
  return [...items].sort((a, b) => {
    if (mode === 'alpha') {
      return a.label.localeCompare(b.label, 'ru', { sensitivity: 'base', numeric: true });
    }
    if (mode === 'desc') return b.value - a.value;
    return a.value - b.value;
  });
}

export function sortBarGroups<T extends { label: string; series: { value: number }[] }>(
  groups: T[],
  mode: SortMode,
): T[] {
  if (!groups.length) return groups;
  const score = (g: T) => g.series.reduce((sum, s) => sum + (Number(s.value) || 0), 0);
  return [...groups].sort((a, b) => {
    if (mode === 'alpha') {
      return a.label.localeCompare(b.label, 'ru', { sensitivity: 'base', numeric: true });
    }
    const diff = score(a) - score(b);
    return mode === 'desc' ? -diff : diff;
  });
}

/** Объединяет ключи всех строк и выстраивает колонки в заданном порядке. */
export function collectTableColumns(
  rows: Record<string, unknown>[],
  preferredOrder: readonly string[] = [],
): string[] {
  if (!rows.length) return [];
  const present = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row)) present.add(key);
  }
  const ordered = preferredOrder.filter((c) => present.has(c));
  for (const key of present) {
    if (!ordered.includes(key)) ordered.push(key);
  }
  return ordered;
}
