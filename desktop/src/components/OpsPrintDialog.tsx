import { useMemo, useState } from 'react';
import {
  buildOpsPrintHtml,
  estimateOpsPrintPages,
  opsPrintPreviewCaption,
  type OpsPrintOrientation,
  type OpsPrintPayload,
} from '../lib/printOpsReport';
import {
  defaultOpsPdfSavePath,
  generateOpsPdfDocument,
  releaseOpsPdfDocument,
  saveAndOpenOpsPdfDocument,
} from '../lib/opsPrintPdf';
import { Modal } from './Modal';
import './OpsPrintDialog.css';

export function OpsPrintDialog({
  payload,
  lastPdfPath,
  onClose,
  onSaved,
  onError,
}: {
  payload: OpsPrintPayload;
  lastPdfPath?: string;
  onClose: () => void;
  onSaved?: (path: string) => void;
  onError?: (message: string) => void;
}) {
  const [printLong, setPrintLong] = useState(true);
  const [printMissingTable, setPrintMissingTable] = useState(true);
  const [orientation, setOrientation] = useState<OpsPrintOrientation>('portrait');
  const [busy, setBusy] = useState(false);

  const opts = useMemo(
    () => ({ printLong, printMissingTable, orientation }),
    [printLong, printMissingTable, orientation],
  );

  const canExport = printLong || printMissingTable;
  const pages = estimateOpsPrintPages(payload, opts);
  const caption = canExport
    ? opsPrintPreviewCaption(payload, opts)
    : 'Выберите хотя бы одну таблицу';

  const orientationHint =
    orientation === 'portrait'
      ? 'Книжная: компактнее, «Услуга» с переносами.'
      : 'Альбомная: шире, меньше переносов в «Услуге».';

  return (
    <Modal title="Печать таблиц" onClose={onClose}>
      <div className="ops-print-dialog">
        <fieldset className="ops-print-fieldset">
          <legend>Таблицы для PDF</legend>
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

        <p className="ops-print-hint">
          Формат A4. PDF сохраняется, открывается для печати; папка с файлом показывается в проводнике.
        </p>
        {canExport ? (
          <p className="ops-print-caption muted">
            {caption} · ≈ {pages} стр.
          </p>
        ) : null}
      </div>

      <div className="modal__actions">
        <button className="btn" type="button" onClick={onClose} disabled={busy}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          type="button"
          disabled={!canExport || busy}
          title="Сохранить PDF и открыть для печати"
          onClick={() => {
            void (async () => {
              setBusy(true);
              let pdfId: string | null = null;
              try {
                const html = buildOpsPrintHtml(payload, opts);
                const pdf = await generateOpsPdfDocument(html, orientation === 'landscape');
                pdfId = pdf.id;
                const defaultPath = defaultOpsPdfSavePath(lastPdfPath, payload.fileName);
                const saved = await saveAndOpenOpsPdfDocument(pdf.id, defaultPath);
                if (saved) {
                  onSaved?.(saved);
                  onClose();
                }
              } catch (e) {
                onError?.(e instanceof Error ? e.message : String(e));
              } finally {
                if (pdfId) void releaseOpsPdfDocument(pdfId);
                setBusy(false);
              }
            })();
          }}
        >
          {busy ? 'Формирование PDF…' : 'PDF'}
        </button>
      </div>
    </Modal>
  );
}
