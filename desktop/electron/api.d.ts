export type AnalizPdfFromHtmlResult = {
  id: string;
  byteLength: number;
};

export type AnalizPdfFromHtmlOptions = {
  html: string;
  landscape?: boolean;
};

export type AnalizPdfSaveOptions = {
  id: string;
  defaultPath?: string;
  openAfterSave?: boolean;
  revealInFolder?: boolean;
};

export type AnalizApi = {
  rpc: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
  openExcelDialog: (opts?: {
    title?: string;
    multiSelections?: boolean;
  }) => Promise<string | string[] | null>;
  saveExcelDialog: (opts?: { defaultPath?: string }) => Promise<string | null>;
  saveTextDialog: (opts?: { defaultPath?: string }) => Promise<string | null>;
  openPath: (filePath: string) => Promise<string>;
  openExternal: (url: string) => Promise<void>;
  getAppVersion: () => Promise<string>;
  getBridgeStatus: () => Promise<{ ok: boolean; detail?: string }>;
  /** Confirm Excel paths from drag-and-drop before emk.load / ksg.load */
  approveLoadPaths?: (paths: string[]) => Promise<string[]>;
  getPathForFile?: (file: File) => string | null;
  syncMenuState?: (state: {
    recent_emk?: string[];
    recent_ksg?: string[];
    recent_ops?: string[];
    date_format?: string;
  }) => Promise<{ ok: boolean }>;
  pdfFromHtml?: (opts: AnalizPdfFromHtmlOptions) => Promise<AnalizPdfFromHtmlResult>;
  pdfRelease?: (id: string) => Promise<{ ok: boolean }>;
  pdfSave?: (opts: AnalizPdfSaveOptions) => Promise<string | null>;
  onMenuAction?: (
    callback: (payload: { action: string; payload?: Record<string, unknown> }) => void,
  ) => () => void;
};

declare global {
  interface Window {
    analiz?: AnalizApi;
  }
}

export {};
