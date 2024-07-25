const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
    runPythonScript: (arg) => ipcRenderer.invoke('run-python', arg),
    cancelPythonScript: (processId) => ipcRenderer.send('cancel-python', processId),
    onPythonScriptProgress: (callback) => ipcRenderer.on('python-script-progress', callback),
    onPythonScriptPid: (callback) => ipcRenderer.on('python-script-pid', callback),
    sendFilePath: (filePath) => ipcRenderer.send('read-file', filePath),
    onFileData: (callback) => ipcRenderer.on('file-data', (event, data) => callback(data))
  })