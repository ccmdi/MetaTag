let filePath;
let processId;
var map;
var filteredAttrs;


// Process file upload
document.getElementById('mapFile').addEventListener('change', (event) => {
    filePath = event.target.files[0].path;
    window.electronAPI.sendFilePath(filePath);
});
  
// Retrieve file data
window.electronAPI.onFileData(async (data) => {
    var json = JSON.parse(data);
    console.log(json);

    let headline = document.querySelector('#infoBox .headline') //.innerHTML = json['customCoordinates'].length + " locations"
    let subline = document.querySelector('#infoBox .subline')

    headline.innerHTML = (json['name'] ? json['name'] : filePath.split('\\').pop().split('.')[0]) + ' - ';
    headline.innerHTML += json.customCoordinates.length + " locations";
    
    const attrRedundant = new Set(['lat', 'lng', 'latitude', 'longitude']);
    const attrSet = new Set(json.customCoordinates.flatMap(obj => 
        Object.entries(obj).filter(([key, value]) => value !== null && !attrRedundant.has(key)).map(([key]) => key)
    ));
    filteredAttrs = Array.from(attrSet);
    subline.innerHTML = filteredAttrs.join(" / ");

    //Update existing filters
    const filterSelects = document.getElementsByClassName('filter');
    Array.from(filterSelects).forEach(select => {
        select.innerHTML = '';
        filteredAttrs.forEach(attr => {
            const option = document.createElement('option');
            option.value = attr;
            option.textContent = attr;
            select.appendChild(option);
        });
    });

    document.getElementById('uploadContainer').style.display = 'none';
    document.getElementById('settingsContainer').style.display = 'flex';

    if(map){
        map.map.remove();
    }
    map = new SVMap(json);
});


document.addEventListener('DOMContentLoaded', function() {
    const progressContainer = document.getElementById('progressContainer');
    const progress = document.getElementById('progress');

    const settings = document.getElementById('settings');
    const options = document.getElementById('options');

    const filters = document.getElementsByClassName('filter');
    const filterValues = document.getElementsByClassName('filterValue');

    const tagButton = document.getElementById('tagButton');

    tagButton.addEventListener('click', function(event) {
        event.preventDefault();
        console.log(progress);
        
        const selectedOptions = [];
        document.querySelectorAll('#options input[type="checkbox"]:checked').forEach((checkbox) => {
            selectedOptions.push(checkbox.value);
        });

        if(!filePath){
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No file path specified!',
                heightAuto: false
            });
            return;
        }
        else if(selectedOptions.length === 0){
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No options selected!',
                heightAuto: false
            });
            return;
        }

        progressContainer.classList.add('progressContainerAnimated');

        const command = "tag";
        window.electronAPI.runPythonScript({ filePath, command, selectedOptions });
        progressContainer.removeAttribute('hidden');
    });

    const addFilterButton = document.getElementById('addFilter');
    const filterScroll = document.querySelector('.filter-scroll');

    addFilterButton.addEventListener('click', function() {
        const newFilterItem = document.createElement('div');
        const select = document.createElement('select');
        select.className = "filter"
        filteredAttrs.forEach(attr => {
            const option = document.createElement('option');
            option.value = attr;
            option.textContent = attr;
            select.appendChild(option);
        });

        newFilterItem.className = 'filter-item';
        newFilterItem.innerHTML = `
            ${select.outerHTML}
            <select class="filter-operation">
                <option value="=">=</option>
                <option value=">">></option>
                <option value="<"><</option>
            </select>
            <textarea class="filter-value" maxlength="8"></textarea>
        `;
        filterScroll.appendChild(newFilterItem);

    });

    // Cancel logic
    document.getElementById('progressCancel').addEventListener('click', () => {
        if (processId) {
            window.electronAPI.cancelPythonScript(processId);
            progressContainer.setAttribute('hidden', true);
        }
    });
});


// Progress logic
window.electronAPI.onPythonScriptProgress((event, message) => {
    const progressRegex = /(\d+)%/;
    const descriptionRegex = /(.*?):/;
    const locsDoneRegex = /(\d+)\//;
    const locsTotalRegex = /\/(\d+)/;
    const errorMessageRegex = /(?:Error|Exception):\s*(.+)/;
    const finishedRegex = /^(Saved to.*)/


    if (!progressRegex.test(message)) {
        const errorMatch = message.match(errorMessageRegex);
        const finishedMatch = message.match(finishedRegex);
        if(errorMatch){
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: errorMatch[1] || 'An error occurred.',
                heightAuto: false
            });
            progressContainer.setAttribute('hidden', true);
        }
        else if(finishedMatch){
            Swal.fire({
                icon: 'success',
                title: 'Success',
                text: finishedMatch[1],
                heightAuto: false
            });
            progressContainer.setAttribute('hidden', true);
        }
    } else {
        const matchProgress = message.match(progressRegex);
        const matchDescription = message.match(descriptionRegex);

        console.log(matchDescription);
        if (matchProgress) {
            console.log(matchProgress[1]);
            // progress.setAttribute('value', message.match(locsDone)[1]/message.match(locsTotal)[1]); // Assuming 'progress' is defined
            progress.style.width = ((message.match(locsDoneRegex)[1]/message.match(locsTotalRegex)[1])*100) + '%';
        }

        if (matchDescription) {
            document.querySelector('#progressContainerDescription').textContent = matchDescription[1]+" ("+message.match(locsDoneRegex)[1]+"/"+message.match(locsTotalRegex)[1]+")";
            console.log(matchDescription[1]);
        }
    }
});

// Process ID logic
window.electronAPI.onPythonScriptPid((event, pid) => {
    processId = pid;
    console.log('Python script PID:', pid);
});








// class FPSMeter {
//     constructor() {
//         this.fps = 0;
//         this.frames = 0;
//         this.lastTime = performance.now();
//     }

//     update() {
//         this.frames++;
//         const time = performance.now();
//         if (time >= this.lastTime + 1000) {
//             this.fps = Math.round((this.frames * 1000) / (time - this.lastTime));
//             this.lastTime = time;
//             this.frames = 0;
//         }
//         return this.fps;
//     }
// }


// const fpsMeter = new FPSMeter();
// let fpsDisplay;

// // Create FPS display element
// function createFPSDisplay() {
//     fpsDisplay = document.createElement('div');
//     fpsDisplay.style.position = 'fixed';
//     fpsDisplay.style.top = '10px';
//     fpsDisplay.style.left = '10px';
//     fpsDisplay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
//     fpsDisplay.style.color = 'white';
//     fpsDisplay.style.padding = '5px';
//     fpsDisplay.style.borderRadius = '5px';
//     fpsDisplay.style.fontFamily = 'Arial, sans-serif';
//     fpsDisplay.style.fontSize = '14px';
//     fpsDisplay.style.zIndex = '9999';
//     document.body.appendChild(fpsDisplay);
// }

// // Update FPS display
// function updateFPSDisplay() {
//     const fps = fpsMeter.update();
//     if (fpsDisplay) {
//         fpsDisplay.textContent = `FPS: ${fps}`;
//     }
//     requestAnimationFrame(updateFPSDisplay);
// }

// // Call these functions to set up the FPS display
// createFPSDisplay();
// updateFPSDisplay();