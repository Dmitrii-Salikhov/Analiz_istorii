import { useMemo, useState } from 'react';
import {
  buildOpsPrintHtml,
  estimateOpsPrintPages,
  opsPrintPreviewCaption,
  printOpsHtml,
  type OpsPrintOrientation,
  type OpsPrintDuplex,
  type OpsPrintPayload,
} from '../lib/printOpsReport';
import { Modal } from './Modal';
import './OpsPrintDialog.css';

export function OpsPrintDialog({
  payload,
  onClose,
  onPrinted,
  onError,
}: {
  payload: OpsPrintPayload;
  onClose: () => void;
  onPrinted?: () => void;
  onError?: (message: string) => void;
}) {
  const [printLong, setPrintLong] = useState(true);
  const [printMissingTable, setPrintMissingTable] = useState(true);
  const [orientation, setOrientation] = useState<OpsPrintOrientation>('portrait');
  const [duplex, setDuplex] = useState<OpsPrintDuplex>('simplex');
  const [busy, setBusy] = useState(false);

  const opts = useMemo(
    () => ({ printLong, printMissingTable, orientation, duplex }),
    [printLong, printMissingTable, orientation, duplex],
  );

  const canPrint = printLong || printMissingTable;
  const pages = estimateOpsPrintPages(payload, opts);
  const caption = canPrint
    ? opsPrintPreviewCaption(payload, opts)
    : 'Выберите хотя бы одну таблицу';

  const orientationHint =
    orientation === 'portrait'
      ? 'Книжная: компактнее, «Услуга» с переносами.'
      : 'Альбомная: шире, меньше переносов в «Услуге».';

  const duplexHint =
    duplex === 'simplex'
      ? 'Односторонняя — подтвердите в диалоге принтера.'
      : duplex === 'longEdge'
        ? 'Двусторонняя (длинный край) — выберите «по длинному краю» в диалоге принтера.'
        : 'Двусторонняя (короткий край) — выберите «по короткому краю» в диалоге принтера.';

  const previewHtml = useMemo(() => {
    if (!canPrint) return '';
    return buildOpsPrintHtml(payload, opts);
  }, [payload, opts, canPrint]);

  return (
    <Modal title="Печать таблиц" wide onClose={onClose}>
      <div className="ops-print-dialog">
        <div className="ops-print-dialog__settings">
          <fieldset className="ops-print-fieldset">
            <legend>Таблицы для печати</legend>
            <label className="ops-print-check">
              <input
                type="checkbox"
                checked={printLong}
                onChange={(e) => setPrintLong(e.target.checked)}
              />
              Длительные операции ({payload.longOps.length})
            </label>
            <label className="ops-print-check">
              <input
                type="checkbox"
                checked={printMissingTable}
                onChange={(e) => setPrintMissingTable(e.target.checked)}
              />
              Без опер.стола ({payload.missingTable.length})
            </label>
          </fieldset>

          <fieldset className="ops-print-fieldset">
            <legend>Ориентация листа</legend>
            <label className="ops-print-radio">
              <input
                type="radio"
                name="ops-print-orientation"
                checked={orientation === 'portrait'}
                onChange={() => setOrientation('portrait')}
              />
              Книжная
            </label>
            <label className="ops-print-radio">
              <input
                type="radio"
                name="ops-print-orientation"
                checked={orientation === 'landscape'}
                onChange={() => setOrientation('landscape')}
              />
              Альбомная
            </label>
            <p className="ops-print-hint">{orientationHint}</p>
          </fieldset>

          <fieldset className="ops-print-fieldset">
            <legend>Двусторонняя печать</legend>
            <label className="ops-print-radio">
              <input
                type="radio"
                name="ops-print-duplex"
                checked={duplex === 'simplex'}
                onChange={() => setDuplex('simplex')}
              />
              Односторонняя
            </label>
            <label className="ops-print-radio">
              <input
                type="radio"
                name="ops-print-duplex"
                checked={duplex === 'longEdge'}
                onChange={() => setDuplex('longEdge')}
              />
              Обе стороны (длинный край)
            </label>
            <label className="ops-print-radio">
              <input
                type="radio"
                name="ops-print-duplex"
                checked={duplex === 'shortEdge'}
                onChange={() => setDuplex('shortEdge')}
              />
              Обе стороны (короткий край)
            </label>
            <p className="ops-print-hint">{duplexHint}</p>
          </fieldset>

          <p className="ops-print-hint">Формат A4. Минимум одна таблица должна быть выбрана.</p>
        </div>

        <div className="ops-print-dialog__preview-wrap">
          <div className="ops-print-dialog__preview-title">Предпросмотр</div>
          {!canPrint ? (
            <div className="ops-print-preview ops-print-preview--empty">
              <div className="ops-print-preview__sheet ops-print-preview__sheet--portrait muted">
                Выберите таблицы
              </div>
            </div>
          ) : (
            <div
              className={`ops-print-preview ops-print-preview--${orientation}`}
              aria-hidden="true"
            >
              <iframe
                className="ops-print-preview__frame"
                title="Предпросмотр печати"
                srcDoc={previewHtml}
              />
            </div>
          )}
          <p className="ops-print-caption">{caption}</p>
          <p className="ops-print-caption muted">≈ {pages} стр.</p>
        </div>
      </div>

      <div className="modal__actions">
        <button className="btn" type="button" onClick={onClose} disabled={busy}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          type="button"
          disabled={!canPrint || busy}
          title="Открыть системный диалог печати"
          onClick={() => {
            void (async () => {
              setBusy(true);
              try {
                const outcome = await printOpsHtml(buildOpsPrintHtml(payload, opts), opts);
                if (outcome === 'printed') {
                  onPrinted?.();
                }
                onClose();
              } catch (e) {
                onError?.(e instanceof Error ? e.message : String(e));
              } finally {
                setBusy(false);
              }
            })();
          }}
        >
          {busy ? 'Печать…' : 'Печать'}
        </button>
      </div>
    </Modal>
  );
}
