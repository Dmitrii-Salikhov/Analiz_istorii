import { useMemo, useState } from 'react';
import { Modal } from './Modal';

const DEFAULT_EMK = [
  'Основные показатели',
  'Возрастные группы',
  'Нарушения (все)',
  'Сводка по врачам',
  'ИДС по врачам',
  'Длительные госпитализации',
  'СКП',
  'Метаданные',
];

export function ExportDialog({
  kind,
  defaultName,
  sections,
  onClose,
  onExport,
}: {
  kind: 'emk' | 'ksg';
  defaultName: string;
  sections?: string[];
  onClose: () => void;
  onExport: (opts: {
    format: 'xlsx' | 'txt';
    sections?: Record<string, boolean>;
  }) => Promise<void>;
}) {
  const list = sections || DEFAULT_EMK;
  const [format, setFormat] = useState<'xlsx' | 'txt'>('xlsx');
  const [selected, setSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(list.map((s) => [s, true])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = useMemo(
    () => (kind === 'emk' ? 'Экспорт отчёта ЭМК' : 'Экспорт отчёта КСГ'),
    [kind],
  );

  return (
    <Modal title={title} hint={`Имя по умолчанию: ${defaultName}`} onClose={onClose}>
      <div className="form-grid">
        <div className="form-row">
          <label>Формат</label>
          <select value={format} onChange={(e) => setFormat(e.target.value as 'xlsx' | 'txt')}>
            <option value="xlsx">Excel (.xlsx)</option>
            <option value="txt">Текст (.txt)</option>
          </select>
        </div>
        {kind === 'emk' && (
          <div className="check-list">
            {list.map((name) => (
              <label key={name}>
                <input
                  type="checkbox"
                  checked={!!selected[name]}
                  onChange={(e) => setSelected((prev) => ({ ...prev, [name]: e.target.checked }))}
                />
                {name}
              </label>
            ))}
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
      </div>
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
              await onExport({
                format,
                sections: kind === 'emk' ? selected : undefined,
              });
              onClose();
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить…
        </button>
      </div>
    </Modal>
  );
}
