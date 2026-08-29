/** Clipboard helpers for Electron renderer. */

export function copySelectionFromDocument(): boolean {
  const sel = window.getSelection();
  if (sel && !sel.isCollapsed) {
    const text = sel.toString();
    if (text.trim()) {
      void copyText(text);
      return true;
    }
  }
  const el = document.activeElement;
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    const start = el.selectionStart;
    const end = el.selectionEnd;
    if (start != null && end != null && start !== end) {
      void copyText(el.value.slice(start, end));
      return true;
    }
  }
  return false;
}

export async function copyText(text: string): Promise<void> {
  if (!text) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

export function rowsToTsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return '';
  const cols = Object.keys(rows[0]);
  const lines = [cols.join('\t')];
  for (const row of rows) {
    lines.push(cols.map((c) => String(row[c] ?? '')).join('\t'));
  }
  return lines.join('\n');
}

function isNumericCode(token: string): boolean {
  return /^\d{3,}$/.test(token);
}

function looksLikeInitials(token: string): boolean {
  return /^[A-Za-zА-Яа-яЁё]\.([A-Za-zА-Яа-яЁё]\.)?$/.test(token.replace(/\s+/g, ''));
}

function isPatronymic(token: string): boolean {
  const t = token.toLowerCase();
  return t.endsWith('ич') || t.endsWith('на') || t.endsWith('кызы') || t.endsWith('оглы');
}

function capitalizeWord(word: string): string {
  if (!word) return word;
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

function initialFromPart(part: string): string {
  const cleaned = part.replace(/\./g, '').trim();
  if (!cleaned) return '';
  return `${cleaned.charAt(0).toUpperCase()}.`;
}

function looksLikeSurname(token: string): boolean {
  const w = token.toLowerCase().replace(/\./g, '');
  if (!w || isPatronymic(token) || looksLikeInitials(token.replace(/\s/g, ''))) {
    return false;
  }
  const suffixes = [
    'ov', 'ev', 'ova', 'eva', 'in', 'ina', 'yn', 'yna', 'iy', 'yy', 'aya', 'yaya',
    'skiy', 'skaya', 'tskiy', 'tskaya', 'enko', 'uk', 'yuk',
    'ов', 'ев', 'ёв', 'ова', 'ева', 'ёва', 'ин', 'ина', 'ын', 'ына',
    'ий', 'ый', 'ая', 'яя', 'ский', 'ская', 'цкий', 'цкая', 'енко', 'ук', 'юк',
  ];
  return suffixes.some((suf) => w.endsWith(suf) && w.length > suf.length + 1);
}

function parsePersonNameParts(parts: string[]): { surname: string; nameParts: string[] } {
  if (parts.length >= 2 && looksLikeInitials(parts[0].replace(/\s/g, ''))) {
    return { surname: parts[parts.length - 1], nameParts: parts.slice(0, -1) };
  }
  if (parts.length >= 2 && isPatronymic(parts[0]) && looksLikeSurname(parts[parts.length - 1])) {
    const middle = parts.slice(1, -1).filter(Boolean);
    const nameParts = middle.length ? [...middle, parts[0]] : [parts[0]];
    return {
      surname: parts[parts.length - 1],
      nameParts,
    };
  }
  if (
    parts.length >= 3 &&
    looksLikeSurname(parts[0]) &&
    isPatronymic(parts[1]) &&
    !looksLikeSurname(parts[2])
  ) {
    return { surname: parts[0], nameParts: [parts[2], parts[1]] };
  }
  if (parts.length >= 3 && isPatronymic(parts[1]) && looksLikeSurname(parts[parts.length - 1])) {
    return { surname: parts[parts.length - 1], nameParts: parts.slice(0, -1) };
  }
  if (parts.length === 2 && looksLikeSurname(parts[0]) && isPatronymic(parts[1])) {
    return { surname: parts[0], nameParts: [parts[1]] };
  }
  if (parts.length === 2 && isPatronymic(parts[0]) && looksLikeSurname(parts[1])) {
    return { surname: parts[1], nameParts: [parts[0]] };
  }
  let surname = parts[0];
  let nameParts = parts.slice(1);
  if (looksLikeInitials(surname) && parts.length >= 2) {
    surname = parts[parts.length - 1];
    nameParts = parts.slice(0, -1);
  }
  return { surname, nameParts };
}

/** «ИВАНОВ ИВАН ИВАНОВИЧ» → «Иванов И.И.»; «Гасанов Магомед Тагирович» → «Гасанов М.Т.». */
export function formatShortPersonName(fullName: unknown): string {
  if (fullName == null) return '—';
  let text = String(fullName).trim();
  if (!text) return '—';
  text = text.replace(/[/\\|]+/g, ' ');
  let parts = text.split(/\s+/).filter(Boolean);
  while (parts.length && isNumericCode(parts[0])) parts = parts.slice(1);
  parts = parts.filter((p) => !isNumericCode(p));
  if (!parts.length) return '—';

  const { surname, nameParts } = parsePersonNameParts(parts);
  const initials = nameParts.map(initialFromPart).filter(Boolean).join('');
  const sur = capitalizeWord(surname);
  return initials ? `${sur} ${initials}` : sur;
}

function shortenOpsReason(reason: unknown): string {
  const s = String(reason ?? '').trim();
  if (!s) return '—';
  const lower = s.toLowerCase();
  if (lower.includes('не занесен') || (lower.includes('без') && lower.includes('стол'))) {
    return 'нет опер.стола';
  }
  // «длительность > 4 ч (даты…)» → без пояснения в скобках
  const cut = s.replace(/\s*\([^)]*даты[^)]*\)\s*/i, '').trim();
  return cut || s;
}

/** Компактные строки для копирования таблиц вкладки «Операции». */
export function opsRowsToCompactCopy(rows: Record<string, unknown>[]): string {
  if (!rows.length) return '';
  return rows
    .map((row) => {
      const kvs = String(row['КВС'] ?? '').trim() || '—';
      const patient = formatShortPersonName(row['Пациент']);
      const surgeon = formatShortPersonName(row['Хирург']);
      const service = String(row['Услуга'] ?? '').trim() || '—';
      const reasonRaw = String(row['Причина'] ?? '');
      const reason = shortenOpsReason(reasonRaw);
      const duration = String(row['Длительность'] ?? '').trim();
      const parts = [
        `КВС (${kvs})`,
        `Пациент (${patient})`,
        `Хирург (${surgeon})`,
        `Услуга (${service})`,
      ];
      if (duration && /длительн/i.test(reasonRaw)) {
        parts.push(`Длительность (${duration})`);
      }
      parts.push(`Причина (${reason})`);
      return parts.join(' ');
    })
    .join('\n');
}
