const NUMERIC_COLUMN_HINTS =
  /сумма|колич|кз|кслп|возраст|доля|итого|пациент|count|sum|total|₽|руб|%/i;

/** Число с разделителями тысяч (ru-RU: 12 947 553). */
export function fmtNum(value: unknown, digits?: number): string {
  const n = parseLocaleNumber(value);
  if (n == null) return '—';
  const d =
    digits ??
    (Number.isInteger(n) ? 0 : Math.min(3, decimalPlaces(n)));
  return n.toLocaleString('ru-RU', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

export function parseLocaleNumber(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (value == null || value === '') return null;
  const s = String(value).trim().replace(/\s/g, '').replace(',', '.');
  if (!s || s === '—') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function decimalPlaces(n: number): number {
  const frac = String(n).split('.')[1];
  return frac ? Math.min(frac.replace(/0+$/, '').length || 0, 3) : 0;
}

function isNumericLikeString(s: string): boolean {
  return /^-?\d[\d\s.,]*$/.test(s.trim());
}

/** Отображение ячейки таблицы: числа — с группировкой разрядов. */
export function formatTableCell(value: unknown, column = ''): string {
  if (value == null || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'ДА' : 'НЕТ';

  const colHint = NUMERIC_COLUMN_HINTS.test(column);

  if (typeof value === 'number') {
    return fmtNum(value);
  }

  const text = String(value).trim();
  if (!text || text === '—') return '—';

  if (colHint || isNumericLikeString(text)) {
    const n = parseLocaleNumber(text);
    if (n != null) {
      const normalized = text.replace(/\s/g, '').replace(',', '.');
      const hasFrac = normalized.includes('.') && !Number.isInteger(n);
      return fmtNum(n, hasFrac ? Math.min(decimalPlaces(n), 3) : 0);
    }
  }

  return text;
}

/** Подпись на столбчатых диаграммах. */
export function fmtChartValue(value: number, unit = ''): string {
  if (!Number.isFinite(value)) return '—';
  const digits = Number.isInteger(value) ? 0 : 1;
  return `${fmtNum(value, digits)}${unit}`;
}
