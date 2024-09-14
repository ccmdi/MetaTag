let filePath;
let processId;
var map;
var filteredAttrs;
let settingsVisible = true;
let infoBoxVisible = true;

// Process file upload
document.getElementById('mapFile').addEventListener('change', (event) => {
    filePath = event.target.files[0].path;
    window.electronAPI.sendFilePath(filePath);
});
  
// Retrieve file data
window.electronAPI.onFileData(async (data) => {
    try {
        var json = JSON.parse(data);
        if (!json.customCoordinates) {
            throw new Error('Missing customCoordinates.');
        }

        document.getElementById('uploadContainer').style.display = 'none';
        document.getElementById('settingsContainer').style.display = 'flex';

        if (map) {
            map.map.remove();
        }
        map = new SVMap(json);
    } catch (error) {
        console.error('Error parsing JSON:', error);
        Swal.fire({
            icon: 'error',
            title: 'Invalid JSON',
            text: error.message,
            heightAuto: false
        });
        document.getElementById('mapFile').value = '';
    }
});


document.addEventListener('DOMContentLoaded', function() {
    const progressContainer = document.getElementById('progressContainer');
    const progress = document.getElementById('progress');

    const settings = document.getElementById('settings');
    const options = document.getElementById('options');

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
        progressContainer.classList.remove('hidden');
    });

    const addFilterButton = document.getElementById('addFilter');
    const filterScroll = document.querySelector('.filter-scroll');

    function createFilterItem() {
        const maxFilters = 10;
        const currentFilters = filterScroll.querySelectorAll('.filter-item').length;
        if (currentFilters >= maxFilters) {
            return null;
        }
    
        const newFilterItem = document.createElement('div');
        newFilterItem.className = 'filter-item';
    
        const selectHtml = Array.from(map.attributes)
            .map(attr => `<option value="${attr}">${formatAttrString(attr)}</option>`)
            .join('');
    
        newFilterItem.innerHTML = `
            <select class="filter">
                ${selectHtml}
            </select>
            <select class="filter-operation">
                <option value="=">=</option>
                <option value="!=">!=</option>
                <option value=">=">>=</option>
                <option value="<="><=</option>
                <option value=">">></option>
                <option value="<"><</option>
            </select>
            <div class="filter-value" contenteditable maxlength="20"></div>
            <button class="delete-filter">X</button>
        `;
        
        newFilterItem.querySelectorAll('select').forEach(el => {
            el.addEventListener('change', () => map.initialize());
        });

        newFilterItem.querySelectorAll('div.filter-value').forEach(el => {
            el.addEventListener('blur', () => map.initialize());
            el.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    el.blur();
                }
            });
        });
    
        const deleteButton = newFilterItem.querySelector('.delete-filter');
        deleteButton.addEventListener('click', function() {
            newFilterItem.remove();
            map.initialize();
        });
    
        return newFilterItem;
    }
    
    addFilterButton.addEventListener('click', function() {
        const newFilterItem = createFilterItem();
        if (newFilterItem) {
            filterScroll.appendChild(newFilterItem);
            map.initialize();
        }
    });

    // Cancel logic
    document.getElementById('progressCancel').addEventListener('click', () => {
        if (processId) {
            window.electronAPI.cancelPythonScript(processId);
            progressContainer.classList.add('hidden');
        }
    });

    const toggleSettings = document.getElementById('toggleSettings');
    const toggleInfoBox = document.getElementById('toggleInfoBox');
    const settingsEl = document.getElementById('settings');
    const infoBox = document.getElementById('infoBox');

    toggleSettings.addEventListener('click', () => {
        settingsVisible = !settingsVisible;
        settingsEl.classList.toggle('hidden', !settingsVisible);
        
        if (map && map.map) {
            map.map.invalidateSize();
        }
    });

    toggleInfoBox.addEventListener('click', () => {
        infoBoxVisible = !infoBoxVisible;
        infoBox.classList.toggle('hidden', !infoBoxVisible);
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
            progressContainer.classList.add('hidden');
        }
        else if(finishedMatch){
            Swal.fire({
                icon: 'success',
                title: 'Success',
                text: finishedMatch[1],
                heightAuto: false
            });
            progressContainer.classList.add('hidden');
        }
    } else {
        const matchProgress = message.match(progressRegex);
        const matchDescription = message.match(descriptionRegex);

        if (matchProgress) {
            console.log(matchProgress[1]);
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



// FPS Counter
const fpsCounter = document.createElement('div');
fpsCounter.id = 'fpsCounter';
fpsCounter.style.position = 'fixed';
fpsCounter.style.top = '10px';
fpsCounter.style.left = '10px';
fpsCounter.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
fpsCounter.style.color = 'white';
fpsCounter.style.padding = '5px 10px';
fpsCounter.style.borderRadius = '5px';
fpsCounter.style.fontSize = '14px';
fpsCounter.style.zIndex = '1000';
document.body.appendChild(fpsCounter);

let frameCount = 0;
let lastTime = performance.now();
let fps = 0;

function updateFPS() {
    frameCount++;
    const currentTime = performance.now();
    const elapsedTime = currentTime - lastTime;

    if (elapsedTime >= 1000) {
        fps = Math.round((frameCount * 1000) / elapsedTime);
        fpsCounter.textContent = `FPS: ${fps}`;
        frameCount = 0;
        lastTime = currentTime;
    }

    requestAnimationFrame(updateFPS);
}

updateFPS();