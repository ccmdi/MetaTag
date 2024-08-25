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
    var json = JSON.parse(data);
    console.log(json);

    document.getElementById('uploadContainer').style.display = 'none';
    document.getElementById('settingsContainer').style.display = 'flex';

    if(map){
        map.map.remove();
    }
    map = new SVMap(json);

    const filterSelects = document.getElementsByClassName('filter');
    Array.from(filterSelects).forEach(select => {
        select.innerHTML = '';
        map.attributes.forEach(attr => {
            const option = document.createElement('option');
            option.value = attr;
            option.textContent = attr;
            select.appendChild(option);
        });
    });
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
        progressContainer.classList.remove('hidden');
    });

    const addFilterButton = document.getElementById('addFilter');
    const filterScroll = document.querySelector('.filter-scroll');

    function createFilterItem() {
        const newFilterItem = document.createElement('div');
        const select = document.createElement('select');
        select.className = "filter"
        map.attributes.forEach(attr => {
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
            <textarea class="filter-value" maxlength="20"></textarea>
            <button class="delete-filter">X</button>
        `;
        
        const deleteButton = newFilterItem.querySelector('.delete-filter');
        deleteButton.addEventListener('click', function() {
            newFilterItem.remove();
            updateFilters();
        });

        return newFilterItem;
    }

    addFilterButton.addEventListener('click', function() {
        const newFilterItem = createFilterItem();
        filterScroll.appendChild(newFilterItem);
        updateFilters();
    });

    function updateFilters() {
        const filterItems = Array.from(filterScroll.getElementsByClassName('filter-item'));
        map.filterMap = filterItems.map(item => {
            const filter = item.querySelector('.filter');
            const operator = item.querySelector('.filter-operation');
            const value = item.querySelector('.filter-value');
            return {
                filter: filter ? filter.value : null,
                operator: operator ? operator.value : null,
                value: value ? value.value : null
            };
        });
        map.initialize();
    }

    filterScroll.addEventListener('change', updateFilters);

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

        console.log(matchDescription);
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