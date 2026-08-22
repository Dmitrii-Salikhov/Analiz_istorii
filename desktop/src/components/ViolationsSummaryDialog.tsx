import { useMemo, useState } from 'react';
import { Modal } from './Modal';

export type ViolationSection = {
  id: string;
  title: string;
  count: number;
  text: string;
};

export function ViolationsSummaryDialog({
  sections,
  onClose,
}: {
  sections: ViolationSection[];
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(sections.map((s) => [s.id, true])),
  );
  const [toast, setToast] = useState<string | null>(null);

  const preview = useMemo(() => {
    return sections
      .filter((s) => selected[s.id])
      .map((s) => s.text)
      .join('\n\n');
  }, [sections, selected]);

  const allSelected = useMemo(
    () => sections.length > 0 && sections.every((s) => selected[s.id]),
    [sections, selected],
  );

  const toggleAll = () => {
    const next = !allSelected;
    setSelected(Object.fromEntries(sections.map((s) => [s.id, next])));
  };

  const copy = async (text: string, okMsg: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setToast(okMsg);
      window.setTimeout(() => setToast(null), 1600);
    } catch {
      setToast('Не удалось скопировать');
    }
  };

  return (
    <Modal title="Сводка нарушений" wide onClose={onClose}>
      {!sections.length ? (
        <div className="muted">Нарушений нет</div>
      ) : (
        <>
          <div className="modal__actions viol-summary-actions">
            <button
              className="btn btn-primary"
              type="button"
              title="Скопировать все категории нарушений"
              onClick={() =>
                void copy(
                  sections.map((s) => s.text).join('\n\n'),
                  'Все нарушения скопированы',
                )
              }
            >
              Копировать всё
            </button>
            <button
              className="btn"
              type="button"
              title="Скопировать только отмеченные категории"
              onClick={() => {
                const blocks = sections.filter((s) => selected[s.id]).map((s) => s.text);
                if (!blocks.length) {
                  setToast('Не выбрано ни одной категории');
                  return;
                }
                void copy(blocks.join('\n\n'), 'Выбранные категории скопированы');
              }}
            >
              Копировать выбранные
            </button>
            <button
              className="btn btn-ghost viol-summary-toggle"
              type="button"
              title={allSelected ? 'Снять отметки со всех категорий' : 'Отметить все категории'}
              onClick={toggleAll}
            >
              {allSelected ? 'Снять все' : 'Выбрать все'}
            </button>
            {toast && <span className="muted viol-summary-toast">{toast}</span>}
          </div>

          <div className="check-list" style={{ margin: '12px 0' }}>
            {sections.map((s) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  checked={!!selected[s.id]}
                  onChange={(e) => setSelected((prev) => ({ ...prev, [s.id]: e.target.checked }))}
                />
                {s.title} ({s.count})
              </label>
            ))}
          </div>

          <div className="viol-preview">{preview || '—'}</div>
        </>
      )}

      <div className="modal__actions">
        <button className="btn" type="button" onClick={onClose}>
          Закрыть
        </button>
      </div>
    </Modal>
  );
}
