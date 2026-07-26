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
};

declare global {
  interface Window {
    analiz?: AnalizApi;
  }
}

export {};
