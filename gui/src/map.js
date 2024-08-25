const config = {
    markerSize: 6,
    attrRedundantTooltip: new Set(['lat', 'lng', 'latitude', 'longitude', 'links', 'panoId', 'country', 'state', 'locality', 'countryCode', 'stateCode'])
}

class SVLink {
    constructor(loc){
        this.url = `https://www.google.com/maps/@${loc.lat},${loc.lng},3a,90y,${loc.heading}h,${90-loc.pitch}t/data=!3m7!1e1!3m5!1s${loc.panoId}!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fpanoid%3D${loc.panoId}%26!7i13312!8i6656`;
    }
}

class SVMap {
    constructor(json) {
        this.json = json;
        this.locations = this.shuffle(json.customCoordinates);
        this.filteredLocations = this.locations;
        this.maxMarkers = 30000;

        this.gridSize = 1; // Grid size in degrees
        this.createGrid();

        const worldBounds = L.latLngBounds(L.latLng(-90, -180), L.latLng(90, 180));

        this.map = L.map('map', {
            zoomControl: false,
            attributionControl: false,
            maxBounds: worldBounds,
            maxBoundsViscosity: 1.0,
            minZoom: 3,  // Set a minimum zoom level
            bounceAtZoomLimits: false  // Prevent bouncing at zoom limits
        });

        L.control.attribution({
            prefix: false,
            position: 'bottomright'
        }).addTo(this.map);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x.png' : '.png'), {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            noWrap: true
        }).addTo(this.map);

        this.updateInfoBox();
        this.fitToBounds();

        this.pixiContainer = new PIXI.ParticleContainer({maxSize: Math.min(this.locations.length, this.maxMarkers), vertices: true});
        this.pixiOverlay = L.pixiOverlay((utils) => {
            const renderer = utils.getRenderer();
            const container = utils.getContainer();
            let markerTexture = renderer.generateTexture(new PIXI.Graphics().beginFill(0x17388e).drawCircle(0, 0, config.markerSize).endFill());
            const project = this.pixiOverlay.utils.latLngToLayerPoint;

            this.pixiContainer.removeChildren();

            const bounds = this.map.getBounds();
            
            const visibleLocations = this.filteredLocations.filter(loc => 
                bounds.contains(L.latLng(loc.lat, loc.lng))
            );

            const locationsToRender = visibleLocations.slice(0, this.maxMarkers);
            
            locationsToRender.forEach((loc) => {
                const markerCoords = project([loc.lat, loc.lng]);
                const marker = new PIXI.Sprite(markerTexture);
                
                marker.interactiveChildren = false;
                marker.anchor.set(0.5, 1);
                marker.position.set(markerCoords.x, markerCoords.y);
    
                
                marker.scale.set(this.markerScaleSize(this.map));

                this.pixiContainer.addChild(marker);
            });
    
            renderer.render(container);
        }, this.pixiContainer, {destroyInteractionManager: true, clearBeforeRender: true});

        // DOM elements
        this.filterContainer = document.getElementById("filterContainer");
        this.filterAdd = document.getElementById("addFilter");
        this.filterMap = new Map();

        this.filterContainer.addEventListener("change", () => {
            const filterItems = Array.from(this.filterContainer.getElementsByClassName('filter-item'));
            this.filterMap = filterItems.map(item => {
                const filter = item.querySelector('.filter');
                const operator = item.querySelector('.filter-operation');
                const value = item.querySelector('.filter-value');
                console.log(value);
                return {
                    filter: filter ? filter.value : null,
                    operator: operator ? operator.value : null,
                    value: value ? value.value : null
                };
            });
            this.initialize();
            console.log(this.filterMap);
        });
        this.filterAdd.addEventListener("click", () => {
            const filterItems = Array.from(this.filterContainer.getElementsByClassName('filter-item'));
            this.filterMap = filterItems.map(item => {
                const filter = item.querySelector('.filter');
                const operator = item.querySelector('.filter-operation');
                const value = item.querySelector('.filter-value');
                console.log(value);
                return {
                    filter: filter ? filter.value : null,
                    operator: operator ? operator.value : null,
                    value: value ? value.value : null
                };
            });
            this.initialize();
            console.log(this.filterMap);
        });

        this.tooltip = document.getElementById("tooltip");

        this.initialize();

        // Tooltip handler
        this.tooltipHandler = (event) => {
            const proximalNode = this.proximalNode(event, 0.1);
            if (!proximalNode.mouseOnMarker){
                tooltip.style.visibility = 'hidden';
                return;
            }
            else {
                tooltip.style.visibility = 'visible';
            }
        
            const workingText = [];
            const { country, state, locality } = proximalNode.nearest;
    
            
            if (country || state || locality) {
                workingText.push(`<strong>${[locality, state, country].filter(Boolean).join(', ')}</strong>`);
            }
        
            for (const [key, value] of Object.entries(proximalNode.nearest)) {
                if(value === null) continue;
                if ((typeof value === "string" || typeof value === "number") && !config.attrRedundantTooltip.has(key)) {
                    if (key === "imageDate" && proximalNode.nearest.timestamp) continue;
                    if (key === 'elevation') {
                        workingText.push(`${formatAttrString(key)}: ${value.toFixed(2)}m`);
                        continue;
                    }
                    if (key === 'heading' || key === 'pitch' || key === 'drivingDirection') {
                        workingText.push(`${formatAttrString(key)}: ${value.toFixed(2)}°`);
                        continue;
                    }
                    if (key === 'timestamp') {
                        const tz = tzlookup(proximalNode.nearest.lat, proximalNode.nearest.lng);
                        const date = new Date(value * 1000);
                        const formattedDate = date.toLocaleString('en-US', {
                            timeZone: tz,
                            year: 'numeric', month: 'short', day: 'numeric',
                            hour: '2-digit', minute: '2-digit', second: '2-digit'
                        });
                        workingText.push(`${formatAttrString(key)}: ${formattedDate}`);
                    } else if (!['country', 'state', 'locality'].includes(key)) {
                        workingText.push(`${formatAttrString(key)}: ${value}`);
                    } 
                }
            }
        
            tooltip.innerHTML = workingText.join('<br>');
            
            if (tooltip.innerHTML) {
                tooltip.style.visibility = 'visible';
                tooltip.style.left = `${event.originalEvent.clientX + 10}px`;
                tooltip.style.top = `${event.originalEvent.clientY + 10}px`;
            } else {
                tooltip.style.visibility = 'hidden';
            }
        };

        // External StreetView link handler
        this.SVLinkHandler = (event) => {
            const proximalNode = this.proximalNode(event, 0.1);
            
            if(proximalNode.nearest && proximalNode.mouseOnMarker){
                const link = new SVLink(proximalNode.nearest);
                console.log(link.url);
                window.open(link.url);
            }
        }

        this.map.on('mousemove', this.tooltipHandler);
        this.map.on('click', this.SVLinkHandler);

        this.pixiOverlay.addTo(this.map);

        this.map.on('drag', () => {
            this.map.panInsideBounds(worldBounds, { animate: false });
        });

        this.map.on('zoom', () => {
            console.log(this.map.getZoom());
            if (this.map.getZoom() < this.map.getMinZoom()) {
                this.map.setZoom(this.map.getMinZoom());
            }
        });

        this.map.on('drag', () => {
            this.map.panInsideBounds(worldBounds, { animate: false });
        });
    }

    shuffle(array) {
        let currentIndex = array.length, randomIndex;
        while (currentIndex != 0) {
            randomIndex = Math.floor(Math.random() * currentIndex);
            currentIndex--;
            [array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
        }
        return array;
    }

    createGrid() {
        this.grid = {};
        this.locations.forEach((loc, index) => {
            const cellX = Math.floor(loc.lng / this.gridSize);
            const cellY = Math.floor(loc.lat / this.gridSize);
            const cellKey = `${cellX},${cellY}`;
            if (!this.grid[cellKey]) {
                this.grid[cellKey] = [];
            }
            this.grid[cellKey].push(index);
        });
    }

    getPrioritizedLocations() {
        const prioritizedLocations = [];
        const cellCounts = Object.values(this.grid).map(indices => indices.length);
        const avgPointsPerCell = Math.floor(cellCounts.reduce((sum, count) => sum + count, 0) / cellCounts.length);

        Object.entries(this.grid).forEach(([cellKey, indices]) => {
            // Shuffle indices to randomize selection within each cell
            const shuffledIndices = this.shuffle([...indices]);
            
            // Select up to avgPointsPerCell locations from each cell
            const selectedIndices = shuffledIndices.slice(0, avgPointsPerCell);
            
            selectedIndices.forEach(index => {
                prioritizedLocations.push({
                    location: this.locations[index],
                    priority: 1 / indices.length // Keep original priority for sorting
                });
            });
        });

        return prioritizedLocations.sort((a, b) => b.priority - a.priority);
    }

    initialize() {
        console.log("Before initialization:", this.locations.slice(0, 10));
        this.filteredLocations = this.locations;
        console.log("After assignment:", this.filteredLocations.slice(0, 10));
        this.filterMap.forEach((filter) => {
            this.filteredLocations = this.filter(this.filteredLocations, filter);
            console.log("After filter:", filter, this.filteredLocations.slice(0, 10));
        });
        console.log("Before kdTree:", this.filteredLocations.slice(0, 10));
        this.tree = new kdTree([...this.filteredLocations], distance, ['lat','lng']);
        console.log("After kdTree:", this.filteredLocations.slice(0, 10));
        this.prioritizedLocations = this.getPrioritizedLocations();
        this.pixiOverlay.redraw();
    }

    filter(locs, { filter, operator, value }) {
        if(filter == null || value == null || filter == "" || value == ""){
            return locs;
        }

        switch(operator) {
            case '=':
                return locs.filter((loc) => loc[filter] == value);
            case '!=':
                return locs.filter((loc) => loc[filter] != value);
            case '>':
                return locs.filter((loc) => loc[filter] > value);
            case '<':
                return locs.filter((loc) => loc[filter] < value);
        }
    }

    proximalNode(event, range) {
        const mouseLatLng = this.map.mouseEventToLatLng(event.originalEvent);
        const mousePosition = this.pixiOverlay.utils.latLngToLayerPoint(mouseLatLng);
        const [nearest, dist] = this.tree.nearest({ lat: mouseLatLng.lat, lng: mouseLatLng.lng }, 1)[0] || [];
        const inRange = (nearest && dist < range);
        // if (!inRange) return {inRange, mouseOnMarker: false, nearest: null, dist: null};

        const markerCoords = this.pixiOverlay.utils.latLngToLayerPoint([nearest.lat, nearest.lng]);
        const mouseDistance = Math.hypot(mousePosition.x - markerCoords.x, mousePosition.y - markerCoords.y);
        const markerRadius = this.markerScaleSize() * config.markerSize;
        const mouseOnMarker = mouseDistance < markerRadius;

        return {inRange, mouseOnMarker, nearest, dist};
    }

    markerScaleSize(){
        const zoom = this.map.getZoom();
        const zoomFactor = 2 ** (9.5 - zoom); //TODO ?
        return zoomFactor;
    }

    updateInfoBox() {
        const headline = document.querySelector('#infoBox .headline');
        const subline = document.querySelector('#infoBox .subline');

        if (headline && subline) {
            headline.textContent = `${this.json.name || filePath.split('\\').pop().split('.')[0]} - ${this.filteredLocations.length} locations`;
            
            this.attributes = new Set();
            this.filteredLocations.forEach(loc => {
                Object.keys(loc).forEach(key => {
                    if (!['lat', 'lng', 'latitude', 'longitude'].includes(key)) {
                        this.attributes.add(key);
                    }
                });
            });
            subline.textContent = Array.from(this.attributes).join(' / ');
        }
    }

    fitToBounds() {
        if (this.filteredLocations.length > 0) {
            const bounds = L.latLngBounds(this.filteredLocations.map(loc => [loc.lat, loc.lng]));
            this.map.fitBounds(bounds);
        }
    }

    updateMap(newFilteredLocations) { // ???
        this.filteredLocations = newFilteredLocations;
        this.updateInfoBox();
        this.fitToBounds();
    }
}