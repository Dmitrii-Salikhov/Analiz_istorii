import { useMemo, useState } from 'react';
import { Modal } from './Modal';
import { DataTable } from './DataTable';

export type ViolationTypeRow = {
  КВС: string;
  пометка: string;
  врач: string;
  нарушение?: string;
  нарушений?: number | string;
};

function hasNoSnilsNote(row: ViolationTypeRow | Record<string, unknown>): boolean {
  return String(row.пометка || '')
    .toLowerCase()
    .includes('снилс');
}

export function ViolationTypeDialog({
  typeLabel,
  rows,
  onClose,
  onOpenInTable,
  showOpenInTable = true,
}: {
  typeLabel: string;
  rows: ViolationTypeRow[];
  onClose: () => void;
  onOpenInTable?: () => void;
  showOpenInTable?: boolean;
}) {
  const [hideNoSnils, setHideNoSnils] = useState(false);

  const noSnilsCount = useMemo(() => rows.filter(hasNoSnilsNote).length, [rows]);

  const visibleRows = useMemo(() => {
    if (!hideNoSnils) return rows;
    return rows.filter((r) => !hasNoSnilsNote(r));
  }, [rows, hideNoSnils]);

  return (
    <Modal
      title={typeLabel}
      hint="Копировать таблицу — кнопка «Копировать» над таблицей"
      wide
      onClose={onClose}
    >
      <div className="modal__actions" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
        {showOpenInTable && onOpenInTable && (
          <button
            type="button"
            className="btn btn-primary"
            title="Открыть вкладку «Нарушения» с фильтром по этому типу"
            onClick={onOpenInTable}
          >
            Открыть в таблице нарушений
          </button>
        )}
        {noSnilsCount > 0 && (
          <button
            type="button"
            className={`btn${hideNoSnils ? ' btn-primary' : ''}`}
            title={
              hideNoSnils
                ? 'Показать снова строки с пометкой «нет СНИЛС»'
                : 'Убрать из списка истории без СНИЛС'
            }
            onClick={() => setHideNoSnils((v) => !v)}
          >
            {hideNoSnils
              ? `Показать без СНИЛС (${noSnilsCount})`
              : `Скрыть без СНИЛС (${noSnilsCount})`}
          </button>
        )}
        <span className="muted" style={{ alignSelf: 'center' }}>
          {visibleRows.length}
          {hideNoSnils && noSnilsCount > 0 ? ` из ${rows.length}` : ''} запис.
        </span>
      </div>
      <DataTable
        rows={visibleRows as unknown as Record<string, unknown>[]}
        empty={
          hideNoSnils
            ? 'Нет записей с СНИЛС (все строки скрыты как «без СНИЛС»)'
            : 'Нет данных'
        }
        filterPlaceholder="Поиск по таблице…"
      />
    </Modal>
  );
}
