import { useMemo, useState } from 'react';
import { copyText, rowsToTsv } from '../lib/clipboard';
import './DataTable.css';

export function DataTable({
  rows,
  empty = 'Нет данных',
  filterable = true,
  copyable = true,
  filterPlaceholder = 'Поиск по таблице…',
  formatCopy,
  getCellClass,
}: {
  rows: Record<string, unknown>[];
  empty?: string;
  filterable?: boolean;
  copyable?: boolean;
  filterPlaceholder?: string;
  /** Если задан — используется вместо TSV при копировании. */
  formatCopy?: (rows: Record<string, unknown>[]) => string;
  getCellClass?: (
    row: Record<string, unknown>,
    col: string,
    rowIndex: number,
  ) => string | undefined;
}) {
  const [query, setQuery] = useState('');
  const [copied, setCopied] = useState(false);

  const columns = useMemo(() => {
    if (!rows.length) return [] as string[];
    return Object.keys(rows[0]);
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      columns.some((c) => String(row[c] ?? '').toLowerCase().includes(q)),
    );
  }, [rows, columns, query]);

  const onCopy = async () => {
    try {
      const text = formatCopy ? formatCopy(filtered) : rowsToTsv(filtered);
      await copyText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  if (!rows.length) {
    return <div className="muted">{empty}</div>;
  }

  return (
    <div className="data-table">
      {(filterable || copyable) && (
        <div className="data-table__toolbar">
          {filterable && (
            <input
              className="data-table__filter"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={filterPlaceholder}
            />
          )}
          {filterable && query && (
            <span className="muted data-table__count">
              {filtered.length} / {rows.length}
            </span>
          )}
          {copyable && (
            <button
              className="btn"
              type="button"
              title="Скопировать видимые строки таблицы в буфер обмена"
              onClick={() => void onCopy()}
            >
              {copied ? 'Скопировано' : 'Копировать'}
            </button>
          )}
        </div>
      )}
      {!filtered.length ? (
        <div className="muted">Нет строк по фильтру</div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => {
                    const cls = getCellClass?.(row, c, i);
                    return (
                      <td key={c} className={cls}>
                        {row[c] == null || row[c] === '' ? '—' : String(row[c])}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
