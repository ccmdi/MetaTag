const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const processMap = new Map();

const path = require('path') 
const env = process.env.NODE_ENV || 'development';

if (env === 'development') { 
    try { 
        require('electron-reloader')(module, { 
            debug: true, 
            watchRenderer: true
        }); 
    } catch (_) { console.log('Error'); }     
} 


function createWindow () {
    console.log(process.env.NODE_ENV);
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      devTools: process.env.NODE_ENV == 'development',
      preload: path.join(__dirname, 'preload.js')
    },
    autoHideMenuBar: true
  });

  win.loadFile('index.html');
  if (process.env.NODE_ENV == 'development'){
    win.toggleDevTools();
  }
//   win.removeMenu();
}

app.whenReady().then(() => {
    createWindow();
 });


ipcMain.handle('run-python', (event, args) => {
    console.log(args.filePath, args.selectedOptions);
    const python = spawn('python', ['metatag.py', args.filePath, ...args.selectedOptions], {
        cwd: path.join(__dirname, '..')
    });
    
    //Store the process reference
    event.sender.send('python-script-pid', python.pid);
    processMap.set(python.pid, python);

    python.stdout.on('data', (data) => {
        console.log(`stdout: ${data}`);
        if(data.toString().includes('Saved to')){
            filePath = data.toString().split('Saved to ')[1].trim();
            fs.readFile(filePath, 'utf-8', (err, data) => {
                if (err) {
                    console.error('Failed to read file', err);
                    return;
                }
                event.sender.send('file-data', data);
            });
        }
        event.sender.send('python-script-progress', data.toString());
    });

    python.stderr.on('data', (data) => {
        console.error(`stderr: ${data}`);
        event.sender.send('python-script-progress', data.toString());
    });

    return new Promise((resolve, reject) => {
        python.on('close', (code) => {
            if (code === 0) {
                resolve('Python script executed successfully.');
            } else {
                reject(new Error('Python script execution failed.'));
            }
        });
    });
});

ipcMain.on('cancel-python', (event, processId) => {
    const python = processMap.get(processId);
    if (python) {
        python.kill(); // Terminate the process
        processMap.delete(processId); // Clean up the process reference
    }
});

ipcMain.on('read-file', (event, filePath) => {
    fs.readFile(filePath, 'utf-8', (err, data) => {
        if (err) {
            console.error('Failed to read file', err);
            return;
        }
        event.sender.send('file-data', data);
    });
});