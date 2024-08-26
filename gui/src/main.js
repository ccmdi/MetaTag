const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const processMap = new Map();

const env = process.env.NODE_ENV || 'development';

if (env === 'development') {
    try {
        require('electron-reloader')(module, {
            debug: true,
            watchRenderer: true
        });
    } catch (_) { console.log('Error'); }
}

function createWindow() {
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

    win.loadFile('src/index.html');
    if (process.env.NODE_ENV == 'development') {
        win.toggleDevTools();
    }
}

function checkPythonAndPip() {
    return new Promise((resolve, reject) => {
        const pythonCheck = spawn('python', ['--version']);
        pythonCheck.on('error', (error) => {
            if (error.code === 'ENOENT') {
                reject(new Error('Python is not installed or not in PATH'));
            } else {
                reject(error);
            }
        });
        pythonCheck.on('close', (code) => {
            if (code !== 0) {
                reject(new Error('Python check failed'));
            } else {
                const pipCheck = spawn('pip', ['--version']);
                pipCheck.on('error', (error) => {
                    if (error.code === 'ENOENT') {
                        reject(new Error('pip is not installed or not in PATH'));
                    } else {
                        reject(error);
                    }
                });
                pipCheck.on('close', (code) => {
                    if (code !== 0) {
                        reject(new Error('pip check failed'));
                    } else {
                        resolve();
                    }
                });
            }
        });
    });
}

function installRequirements() {
    return new Promise((resolve, reject) => {
        const requirementsPath = path.join(process.resourcesPath, 'requirements.txt');
        const flagPath = path.join(process.resourcesPath, 'requirements_installed.flag');

        if (fs.existsSync(flagPath)) {
            console.log('Requirements already installed.');
            resolve();
            return;
        }

        console.log('Installing requirements...');
        const pip = spawn('pip', ['install', '-r', requirementsPath]);

        pip.stdout.on('data', (data) => {
            console.log(`stdout: ${data}`);
        });

        pip.stderr.on('data', (data) => {
            console.error(`stderr: ${data}`);
        });

        pip.on('close', (code) => {
            if (code === 0) {
                fs.writeFileSync(flagPath, 'Requirements installed');
                console.log('Requirements installed successfully.');
                resolve();
            } else {
                console.error(`pip process exited with code ${code}`);
                reject(new Error(`pip process exited with code ${code}`));
            }
        });
    });
}

app.whenReady().then(() => {
    checkPythonAndPip()
        .then(() => installRequirements())
        .then(() => {
            createWindow();
        })
        .catch((error) => {
            dialog.showErrorBox('Setup Error', `Error: ${error.message}\n\nPlease install Python and pip to use this application.`);
            app.quit();
        });
});

ipcMain.handle('run-python', (event, args) => {
    const pythonScriptPath = path.join(process.resourcesPath, 'metatag.py');
    const python = spawn('python', [pythonScriptPath, args.command, args.filePath, ...args.selectedOptions], {
        cwd: process.resourcesPath
    });
    
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
        python.kill();
        processMap.delete(processId);
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

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') app.quit();
});