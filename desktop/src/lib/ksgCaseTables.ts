/** Порядок колонок в таблицах дешёвых/дорогих случаев КСГ. */
export const KSG_CASE_COLUMN_ORDER = [
  '№ талона',
  'ФИО пациента',
  'Врач',
  'Услуга',
  'Сумма к оплате',
  'Дата рождения',
  'Отделение',
] as const;

const SERVICE_ABSENT = 'Услуга отсутствует';

function hasServiceText(value: unknown): boolean {
  const text = String(value ?? '').trim();
  return Boolean(text && text !== '—');
}

/** Гарантирует колонку «Услуга» даже если бэкенд ещё не пересчитан. */
export function normalizeKsgCaseRows(
  rows: Record<string, unknown>[],
): Record<string, unknown>[] {
  return rows.map((row) => {
    const out = { ...row };
    if (hasServiceText(out['Услуга'])) {
      if ('Код услуги' in out) delete out['Код услуги'];
      return out;
    }
    const code = out['Код услуги'];
    if (hasServiceText(code)) {
      out['Услуга'] = String(code).trim();
    } else {
      out['Услуга'] = SERVICE_ABSENT;
    }
    if ('Код услуги' in out) delete out['Код услуги'];
    return out;
  });
}

export function orderKsgCaseColumns(columns: string[]): string[] {
  const present = new Set(columns);
  const ordered: string[] = KSG_CASE_COLUMN_ORDER.filter((c) => present.has(c));
  for (const c of columns) {
    if (!ordered.includes(c)) ordered.push(c);
  }
  return ordered;
}
