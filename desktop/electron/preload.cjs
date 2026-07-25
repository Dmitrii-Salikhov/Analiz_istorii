const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('analiz', {
  rpc: (method, params) => ipcRenderer.invoke('bridge:rpc', method, params || {}),
  openExcelDialog: (opts) => ipcRenderer.invoke('dialog:openExcel', opts || {}),
  saveExcelDialog: (opts) => ipcRenderer.invoke('dialog:saveExcel', opts || {}),
  saveTextDialog: (opts) => ipcRenderer.invoke('dialog:saveText', opts || {}),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  openPath: (filePath) => ipcRenderer.invoke('shell:openPath', filePath),
  getAppVersion: () => ipcRenderer.invoke('app:getVersion'),
  getBridgeStatus: () => ipcRenderer.invoke('bridge:status'),
  getPathForFile: (file) => {
    try {
      return webUtils.getPathForFile(file);
    } catch {
      return null;
    }
  },
});
