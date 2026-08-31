import { useEffect, useMemo, useState } from 'react';
import { copyText, rowsToTsv } from '../lib/clipboard';
import { formatTableCell } from '../lib/format';
import { collectTableColumns, pickSortColumn, sortRows, type SortMode } from '../lib/sortUtils';
import { SortControls } from './SortControls';
import './DataTable.css';

export function DataTable({
  rows,
  empty = 'Нет данных',
  filterable = true,
  copyable = true,
  sortable = true,
  filterPlaceholder = 'Поиск по таблице…',
  initialQuery = '',
  queryResetKey,
  formatCopy,
  getCellClass,
  defaultSortMode = 'asc',
  sortColumn: sortColumnProp,
  columnOrder,
}: {
  rows: Record<string, unknown>[];
  empty?: string;
  filterable?: boolean;
  copyable?: boolean;
  sortable?: boolean;
  filterPlaceholder?: string;
  /** Начальный / внешний фильтр (например, тип нарушения). */
  initialQuery?: string;
  /** При смене ключа подставляется initialQuery заново. */
  queryResetKey?: string | number;
  /** Если задан — используется вместо TSV при копировании. */
  formatCopy?: (rows: Record<string, unknown>[]) => string;
  getCellClass?: (
    row: Record<string, unknown>,
    col: string,
    rowIndex: number,
  ) => string | undefined;
  defaultSortMode?: SortMode;
  /** Колонка для сортировки; по умолчанию — первая. */
  sortColumn?: string;
  /** Предпочитаемый порядок колонок (объединяет ключи всех строк). */
  columnOrder?: readonly string[];
}) {
  const [query, setQuery] = useState(initialQuery);
  const [copied, setCopied] = useState(false);
  const [sortMode, setSortMode] = useState<SortMode>(defaultSortMode);

  useEffect(() => {
    if (queryResetKey === undefined) return;
    setQuery(initialQuery);
  }, [queryResetKey, initialQuery]);

  const columns = useMemo(
    () => collectTableColumns(rows, columnOrder),
    [rows, columnOrder],
  );

  const sortColumn = useMemo(() => {
    if (sortColumnProp && columns.includes(sortColumnProp)) return sortColumnProp;
    return pickSortColumn(columns, rows, sortMode);
  }, [sortColumnProp, columns, rows, sortMode]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      columns.some((c) => String(row[c] ?? '').toLowerCase().includes(q)),
    );
  }, [rows, columns, query]);

  const sorted = useMemo(() => {
    if (!sortable || !sortColumn) return filtered;
    return sortRows(filtered, sortColumn, sortMode);
  }, [filtered, sortColumn, sortMode, sortable]);

  const onCopy = async () => {
    try {
      const forCopy = sorted.map((row) => {
        const out: Record<string, unknown> = {};
        for (const c of columns) out[c] = formatTableCell(row[c], c);
        return out;
      });
      const text = formatCopy ? formatCopy(sorted) : rowsToTsv(forCopy);
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

  const showToolbar = filterable || copyable || sortable;

  return (
    <div className="data-table">
      {showToolbar && (
        <div className="data-table__toolbar">
          {sortable && (
            <SortControls mode={sortMode} onChange={setSortMode} />
          )}
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
              {sorted.length} / {rows.length}
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
      {!sorted.length ? (
        <div className="muted">Нет строк по фильтру</div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c} data-col={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => {
                    const cls = getCellClass?.(row, c, i);
                    return (
                      <td key={c} className={cls} data-col={c}>
                        {formatTableCell(row[c], c)}
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
