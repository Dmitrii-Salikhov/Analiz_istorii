import { formatShortPersonName } from './clipboard';

export type OpsPrintOrientation = 'portrait' | 'landscape';
export type OpsPrintDuplex = 'simplex' | 'longEdge' | 'shortEdge';

export type OpsPrintOptions = {
  printLong: boolean;
  printMissingTable: boolean;
  orientation: OpsPrintOrientation;
  duplex: OpsPrintDuplex;
};

export type OpsPrintRow = Record<string, unknown>;

export type OpsPrintPayload = {
  fileName: string;
  department?: string;
  scope?: 'single' | 'multi' | 'all';
  departmentsInScope?: string[];
  longOpHours: number;
  longOps: OpsPrintRow[];
  missingTable: OpsPrintRow[];
};

const LONG_COLUMNS = [
  { key: 'КВС', label: 'КВС №', width: '9%' },
  { key: 'Пациент', label: 'Пациент', width: '11%', format: 'person' },
  { key: 'Хирург', label: 'Хирург', width: '11%', format: 'person' },
  { key: 'Услуга', label: 'Услуга', width: '38%', format: 'service' },
  { key: 'Длительность', label: 'Длительность', width: '10%' },
  { key: 'Опер.стол', label: 'Опер стол', width: '7%' },
  { key: 'Отделение', label: 'Отделение', width: '14%', format: 'dept' },
] as const;

const MISSING_COLUMNS = [
  { key: 'КВС', label: 'КВС №', width: '10%' },
  { key: 'Пациент', label: 'Пациент', width: '12%', format: 'person' },
  { key: 'Хирург', label: 'Хирург', width: '12%', format: 'person' },
  { key: 'Услуга', label: 'Услуга', width: '45%', format: 'service' },
  { key: 'Опер.стол', label: 'Опер стол', width: '8%' },
  { key: 'Отделение', label: 'Отделение', width: '13%', format: 'dept' },
] as const;

const LONG_COLUMNS_PORTRAIT = LONG_COLUMNS;
const MISSING_COLUMNS_PORTRAIT = MISSING_COLUMNS;

const LONG_COLUMNS_LANDSCAPE = [
  { key: 'КВС', label: 'КВС №', width: '8%' },
  { key: 'Пациент', label: 'Пациент', width: '10%', format: 'person' },
  { key: 'Хирург', label: 'Хирург', width: '10%', format: 'person' },
  { key: 'Услуга', label: 'Услуга', width: '44%', format: 'service' },
  { key: 'Длительность', label: 'Длительность', width: '9%' },
  { key: 'Опер.стол', label: 'Опер стол', width: '7%' },
  { key: 'Отделение', label: 'Отделение', width: '12%', format: 'dept' },
] as const;

const MISSING_COLUMNS_LANDSCAPE = [
  { key: 'КВС', label: 'КВС №', width: '9%' },
  { key: 'Пациент', label: 'Пациент', width: '11%', format: 'person' },
  { key: 'Хирург', label: 'Хирург', width: '11%', format: 'person' },
  { key: 'Услуга', label: 'Услуга', width: '50%', format: 'service' },
  { key: 'Опер.стол', label: 'Опер стол', width: '8%' },
  { key: 'Отделение', label: 'Отделение', width: '11%', format: 'dept' },
] as const;

function columnsFor(
  kind: 'long' | 'missing',
  orientation: OpsPrintOrientation,
): readonly (typeof LONG_COLUMNS)[number][] | readonly (typeof MISSING_COLUMNS)[number][] {
  if (kind === 'long') {
    return orientation === 'landscape' ? LONG_COLUMNS_LANDSCAPE : LONG_COLUMNS_PORTRAIT;
  }
  return orientation === 'landscape' ? MISSING_COLUMNS_LANDSCAPE : MISSING_COLUMNS_PORTRAIT;
}

const DEPT_REPLACEMENTS: [RegExp, string][] = [
  [/оториноларингологическ/gi, 'Оториноларинг.'],
  [/травматологическ/gi, 'Травматол.'],
  [/офтальмологическ/gi, 'Офтальмол.'],
  [/хирургическ/gi, 'Хир.'],
  [/отделение/gi, 'отд.'],
  [/подразделение/gi, 'подр.'],
];

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function shortenDepartment(raw: unknown): string {
  let s = String(raw ?? '').trim();
  if (!s) return '—';
  const parts = s.split('/').map((p) => p.trim()).filter(Boolean);
  if (parts.length > 1) {
    s = parts[parts.length - 1];
  }
  for (const [re, rep] of DEPT_REPLACEMENTS) {
    s = s.replace(re, rep);
  }
  return s.trim() || '—';
}

function formatCell(
  row: OpsPrintRow,
  col: (typeof LONG_COLUMNS)[number] | (typeof MISSING_COLUMNS)[number],
): string {
  const raw = row[col.key];
  if ('format' in col && col.format === 'person') {
    return escapeHtml(formatShortPersonName(raw));
  }
  if ('format' in col && col.format === 'dept') {
    return escapeHtml(shortenDepartment(raw));
  }
  if ('format' in col && col.format === 'service') {
    return escapeHtml(String(raw ?? '').trim() || '—');
  }
  const text = String(raw ?? '').trim();
  return escapeHtml(text || '—');
}

function printTimestamp(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function buildHeaderHtml(payload: OpsPrintPayload): string {
  const lines: string[] = [
    '<h1 class="doc-title">Анализ операций</h1>',
    `<div class="meta-line"><strong>Файл:</strong> ${escapeHtml(payload.fileName || '—')}</div>`,
  ];
  const scope = payload.scope || 'single';
  const inScope = payload.departmentsInScope?.filter(Boolean) || [];
  if ((scope === 'all' || scope === 'multi') && inScope.length > 0) {
    lines.push(
      `<div class="meta-line"><strong>Сводка по ${inScope.length} отделениям:</strong></div>`,
      '<ul class="dept-list">',
      ...inScope.map((d) => `<li>${escapeHtml(d)}</li>`),
      '</ul>',
    );
  } else if (payload.department) {
    lines.push(
      `<div class="meta-line"><strong>Отделение:</strong> ${escapeHtml(payload.department)}</div>`,
    );
  }
  lines.push(
    `<div class="meta-line"><strong>Порог длительности:</strong> &gt; ${escapeHtml(payload.longOpHours)} ч</div>`,
    `<div class="meta-line"><strong>Дата печати:</strong> ${escapeHtml(printTimestamp())}</div>`,
  );
  return `<header class="doc-header">${lines.join('')}</header>`;
}

function buildTableSectionHtml(
  title: string,
  count: number,
  rows: OpsPrintRow[],
  columns: readonly (typeof LONG_COLUMNS)[number][] | readonly (typeof MISSING_COLUMNS)[number][],
  sectionClass: string,
): string {
  const head = columns
    .map(
      (c) =>
        `<th style="width:${c.width}">${escapeHtml(c.label)}</th>`,
    )
    .join('');
  const body =
    rows.length > 0
      ? rows
          .map(
            (row) =>
              `<tr>${columns.map((c) => `<td class="col-${c.key === 'Услуга' ? 'service' : c.key === 'Отделение' ? 'dept' : 'plain'}">${formatCell(row, c)}</td>`).join('')}</tr>`,
          )
          .join('')
      : '';
  const empty = rows.length === 0 ? '<p class="empty-note">Нет данных</p>' : '';
  return `
<section class="ops-section ${sectionClass}">
  <h2 class="section-title">${escapeHtml(title)} — всего нарушений: ${count}</h2>
  <table class="ops-table">
    <thead><tr>${head}</tr></thead>
    <tbody>${body}</tbody>
  </table>
  ${empty}
</section>`;
}

export function estimateOpsPrintPages(
  payload: OpsPrintPayload,
  opts: OpsPrintOptions,
): number {
  let units = 10;
  if (opts.printLong) units += 6 + Math.max(payload.longOps.length, 1);
  if (opts.printMissingTable) units += 6 + Math.max(payload.missingTable.length, 1);
  const perPage = opts.orientation === 'landscape' ? 30 : 40;
  return Math.max(1, Math.ceil(units / perPage));
}

export function opsPrintPreviewCaption(
  payload: OpsPrintPayload,
  opts: OpsPrintOptions,
): string {
  const pages = estimateOpsPrintPages(payload, opts);
  const tables = (opts.printLong ? 1 : 0) + (opts.printMissingTable ? 1 : 0);
  const orient = opts.orientation === 'landscape' ? 'альбомная' : 'книжная';
  const duplexLabel =
    opts.duplex === 'longEdge'
      ? ' · двусторонняя (длинный край)'
      : opts.duplex === 'shortEdge'
        ? ' · двусторонняя (короткий край)'
        : '';
  const serviceWidth = opts.orientation === 'landscape' ? '~50%' : opts.printMissingTable && !opts.printLong ? '~45%' : '~38%';
  return `Стр. 1${pages > 1 ? `–${pages}` : ''} · A4 ${orient}${duplexLabel} · ${tables} ${tables === 1 ? 'таблица' : 'таблицы'} · «Услуга» ${serviceWidth}`;
}

export function buildOpsPrintHtml(payload: OpsPrintPayload, opts: OpsPrintOptions): string {
  const pageSize = opts.orientation === 'landscape' ? 'A4 landscape' : 'A4 portrait';
  const sections: string[] = [buildHeaderHtml(payload)];
  if (opts.printLong) {
    sections.push(
      buildTableSectionHtml(
        'Длительные операции',
        payload.longOps.length,
        payload.longOps,
        columnsFor('long', opts.orientation),
        'ops-section--long',
      ),
    );
  }
  if (opts.printMissingTable) {
    sections.push(
      buildTableSectionHtml(
        'Без опер.стола',
        payload.missingTable.length,
        payload.missingTable,
        columnsFor('missing', opts.orientation),
        'ops-section--missing',
      ),
    );
  }
  return `<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<title>Печать операций</title>
<style>
  @page {
    size: ${pageSize};
    margin: 12mm 10mm 16mm 10mm;
    @bottom-right {
      content: "Стр. " counter(page) " из " counter(pages);
      font: 10pt/1 Arial, sans-serif;
      color: #333;
    }
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    font: 12pt/1.05 Arial, "Liberation Sans", sans-serif;
    color: #000;
    background: #fff;
  }
  .doc-title {
    margin: 0 0 6px;
    font-size: 14pt;
    font-weight: 700;
    line-height: 1.1;
  }
  .doc-header { margin-bottom: 10px; }
  .meta-line { margin: 0 0 2px; line-height: 1.15; }
  .dept-list {
    margin: 2px 0 6px 18px;
    padding: 0;
    line-height: 1.15;
  }
  .dept-list li { margin: 0 0 1px; }
  .ops-section {
    margin: 0 0 8px;
    page-break-inside: auto;
  }
  .section-title {
    margin: 0 0 4px;
    font-size: 12pt;
    font-weight: 700;
    line-height: 1.1;
    break-after: avoid;
    page-break-after: avoid;
  }
  .ops-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 12pt;
    line-height: 1.05;
  }
  .ops-table thead {
    display: table-header-group;
  }
  .ops-table tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .ops-table th,
  .ops-table td {
    border: 1px solid #333;
    padding: 1px 3px;
    vertical-align: top;
    text-align: left;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }
  .ops-table th {
    font-weight: 700;
    background: #eee;
  }
  .col-service { word-break: break-word; }
  .col-dept { word-break: break-word; }
  .empty-note {
    margin: 4px 0 0;
    font-style: italic;
    line-height: 1.1;
  }
</style>
</head>
<body>
${sections.join('\n')}
</body>
</html>`;
}

export type OpsPrintOutcome = 'printed' | 'cancelled';

async function printOpsHtmlViaIframe(html: string): Promise<OpsPrintOutcome> {
  return new Promise((resolve, reject) => {
    const iframe = document.createElement('iframe');
    iframe.setAttribute('aria-hidden', 'true');
    iframe.title = 'Печать операций';
    // Нулевой размер блокирует диалог печати в Electron; держим лист за экраном.
    iframe.style.cssText =
      'position:fixed;left:-10000px;top:0;width:794px;height:1123px;border:0;opacity:0;pointer-events:none';
    document.body.appendChild(iframe);
    const win = iframe.contentWindow;
    const doc = iframe.contentDocument;
    if (!win || !doc) {
      document.body.removeChild(iframe);
      reject(new Error('Не удалось подготовить печать'));
      return;
    }
    let done = false;
    const cleanup = () => {
      window.setTimeout(() => {
        if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
      }, 500);
    };
    const finish = (outcome: OpsPrintOutcome) => {
      if (done) return;
      done = true;
      window.removeEventListener('afterprint', onAfterPrint);
      win.removeEventListener('afterprint', onAfterPrint);
      cleanup();
      resolve(outcome);
    };
    const onAfterPrint = () => finish('printed');
    window.addEventListener('afterprint', onAfterPrint, { once: true });
    win.addEventListener('afterprint', onAfterPrint, { once: true });
    doc.open();
    doc.write(html);
    doc.close();
    window.setTimeout(() => {
      try {
        win.focus();
        win.print();
      } catch (e) {
        if (!done) {
          done = true;
          window.removeEventListener('afterprint', onAfterPrint);
          win.removeEventListener('afterprint', onAfterPrint);
          cleanup();
        }
        reject(e instanceof Error ? e : new Error(String(e)));
      }
    }, 200);
  });
}

export async function printOpsHtml(
  html: string,
  _opts?: Pick<OpsPrintOptions, 'orientation' | 'duplex'>,
): Promise<OpsPrintOutcome> {
  // Electron webContents.print() на скрытом окне завершается без диалога принтера.
  // Надёжный путь — iframe + window.print() в главном renderer (как в v1.3.8).
  return printOpsHtmlViaIframe(html);
}

export function printOpsReport(payload: OpsPrintPayload, opts: OpsPrintOptions): Promise<OpsPrintOutcome> {
  const html = buildOpsPrintHtml(payload, opts);
  return printOpsHtml(html, opts);
}
