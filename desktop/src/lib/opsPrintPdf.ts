export type OpsPdfDocument = {
  id: string;
  byteLength: number;
};

function electronIpcUnavailableMessage(err: unknown): string | null {
  const msg = err instanceof Error ? err.message : String(err);
  if (/No handler registered for 'pdf:/.test(msg)) {
    return 'Перезапустите desktop-приложение (npm run dev): обновлён код Electron main без перезапуска процесса';
  }
  return null;
}

export async function generateOpsPdfDocument(
  html: string,
  landscape: boolean,
): Promise<OpsPdfDocument> {
  const api = window.analiz?.pdfFromHtml;
  if (!api) {
    throw new Error('PDF доступен только в desktop-приложении Electron');
  }
  try {
    const result = await api({ html, landscape });
    return {
      id: result.id,
      byteLength: result.byteLength,
    };
  } catch (e) {
    const hint = electronIpcUnavailableMessage(e);
    throw new Error(hint ?? (e instanceof Error ? e.message : String(e)));
  }
}

export async function releaseOpsPdfDocument(id: string | null | undefined): Promise<void> {
  if (!id) return;
  const api = window.analiz?.pdfRelease;
  if (!api) return;
  await api(id);
}

export async function saveAndOpenOpsPdfDocument(
  id: string,
  defaultPath: string,
): Promise<string | null> {
  const api = window.analiz?.pdfSave;
  if (!api) {
    throw new Error('Сохранение PDF доступно только в desktop-приложении Electron');
  }
  return api({ id, defaultPath, openAfterSave: true, revealInFolder: true });
}

export function defaultOpsPdfFileName(sourceFileName: string): string {
  const base = String(sourceFileName || 'операции')
    .replace(/\.[^.]+$/, '')
    .replace(/[<>:"/\\|?*]/g, '_')
    .trim();
  return `Печать_${base || 'операции'}.pdf`;
}

export function defaultOpsPdfSavePath(
  lastSavedPath: string | undefined,
  sourceFileName: string,
): string {
  const fileName = defaultOpsPdfFileName(sourceFileName);
  const prev = String(lastSavedPath || '').trim();
  if (!prev) return fileName;
  const slash = Math.max(prev.lastIndexOf('/'), prev.lastIndexOf('\\'));
  if (slash <= 0) return fileName;
  const dir = prev.slice(0, slash);
  return `${dir}/${fileName}`;
}