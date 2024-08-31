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
            minZoom: 3,
            bounceAtZoomLimits: false
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

        this.tooltip = document.getElementById("tooltip");

        this.initialize();

        // Tooltip handler
        this.tooltipHandler = (event) => {
            const proximalNode = this.proximalNode(event, 0.1);
            if (!proximalNode.mouseOnMarker) {
                this.tooltip.style.visibility = 'hidden';
                return;
            }

            const workingText = [];
            const { country, state, locality, lat, lng } = proximalNode.nearest;

            const locationHead = [locality, state, country].filter(Boolean);
            if (locationHead.length) {
                workingText.push(`<strong>${locationHead.join(', ')}</strong>`);
            }

            const formatValue = (key, value) => {
                if (key === 'elevation') return `${value.toFixed(2)}m`;
                if (['heading', 'pitch', 'drivingDirection', 'azimuth', 'altitude'].includes(key)) {
                    const degrees = `${value.toFixed(2)}°`;
                    return ['azimuth', 'heading', 'drivingDirection'].includes(key) 
                        ? `${degrees} ${getOctodirectionalArrow(value)}`
                        : degrees;
                }
                if (key === 'timestamp') {
                    const tz = tzlookup(lat, lng);
                    return new Date(value * 1000).toLocaleString('en-US', {
                        timeZone: tz,
                        year: 'numeric', month: 'short', day: 'numeric',
                        hour: '2-digit', minute: '2-digit', second: '2-digit'
                    });
                }
                return value;
            };

            for (const [key, value] of Object.entries(proximalNode.nearest)) {
                if (value === null || config.attrRedundantTooltip.has(key)) continue;
                if (key === "imageDate" && proximalNode.nearest.timestamp) continue;
                if (['country', 'state', 'locality'].includes(key)) continue;
                if (typeof value === "string" || typeof value === "number") {
                    workingText.push(`${formatAttrString(key)}: ${formatValue(key, value)}`);
                }
            }

            this.tooltip.innerHTML = workingText.join('<br>');
            this.tooltip.style.visibility = 'visible';
            this.tooltip.style.left = `${event.originalEvent.clientX + 10}px`;
            this.tooltip.style.top = `${event.originalEvent.clientY + 10}px`;
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
            const shuffledIndices = this.shuffle([...indices]);
            
            const selectedIndices = shuffledIndices.slice(0, avgPointsPerCell);
            
            selectedIndices.forEach(index => {
                prioritizedLocations.push({
                    location: this.locations[index],
                    priority: 1 / indices.length
                });
            });
        });

        return prioritizedLocations.sort((a, b) => b.priority - a.priority);
    }

    initialize() {
        this.updateFilterSelect();
        this.applyFilters();
        this.tree = new kdTree([...this.filteredLocations], distance, ['lat','lng']);
        this.prioritizedLocations = this.getPrioritizedLocations();
        this.pixiOverlay.redraw();
        this.updateInfoBox();
        // this.fitToBounds();
    }

    applyFilters() {
        this.filteredLocations = this.locations;
        const filters = this.getActiveFilters();
        filters.forEach(filter => {
            this.filteredLocations = this.filterLocations(this.filteredLocations, filter);
        });
    }

    getActiveFilters() {
        const filterItems = this.filterContainer.getElementsByClassName('filter-item');
        return Array.from(filterItems)
            .map(item => ({
                filter: item.querySelector('.filter').value,
                operator: item.querySelector('.filter-operation').value,
                value: item.querySelector('.filter-value').innerText.trim()
            }))
            .filter(filter => filter.filter && filter.value !== "");
    }

    filterLocations(locations, { filter, operator, value }) {
        const numValue = parseFloat(value);
        return locations.filter(loc => {
            const locValue = loc[filter];
            switch(operator) {
                case '=':
                    return locValue == value;
                case '!=':
                    return locValue != value;
                case '>':
                    return !isNaN(numValue) && locValue > numValue;
                case '<':
                    return !isNaN(numValue) && locValue < numValue;
                default:
                    return true;
            }
        });
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
    
    /**
     * Updates the info box with the current state of the map.
     */
    updateInfoBox() {
        const headline = document.querySelector('#infoBox .headline');
        const subline = document.querySelector('#infoBox .subline');

        if (headline && subline) {
            headline.innerHTML = `${this.json.name || filePath.split('\\').pop().split('.')[0]} - ${this.locations.length} locations` + 
                (this.filteredLocations.length < this.locations.length ? 
                ` <span style="color: #888888;">(${this.filteredLocations.length})</span>` : '');
            
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

    /**
     * Fits the map to the bounds of the filtered locations.
     */
    fitToBounds() {
        if (this.filteredLocations.length > 0) {
            const bounds = L.latLngBounds(this.filteredLocations.map(loc => [loc.lat, loc.lng]));
            this.map.fitBounds(bounds);
        }
    }

    /**
     * Updates the filter select dropdowns with the current map attributes.
     */
    updateFilterSelect() {
        const filterItems = this.filterContainer.getElementsByClassName('filter-item');
        this.filterMap = Array.from(filterItems, item => ({
            filter: formatAttrString(item.querySelector('.filter')?.value),
            operator: item.querySelector('.filter-operation')?.value,
            value: item.querySelector('.filter-value')?.innerText
        }));

        const filterSelects = this.filterContainer.getElementsByClassName('filter');
        if (this.cachedAttributesHTML === undefined) {
            this.cachedAttributesHTML = Array.from(this.attributes)
                .map(attr => `<option value="${attr}">${formatAttrString(attr)}</option>`)
                .join('');
        }

        Array.from(filterSelects).forEach(select => {
            const currentValue = select.value;
            select.innerHTML = this.cachedAttributesHTML;
            if (currentValue && Array.from(select.options).some(option => option.value === currentValue)) {
                select.value = currentValue;
            }
        });
    }
}