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
        this.locations = shuffle(json.customCoordinates);
        this.filteredLocations = this.locations;
        this.filterMap = new Map();
        this.tree = new kdTree([...this.locations], distance, ['lat','lng']);
        
        // Performance caps
        this.maxMarkers = 30000;

        const worldBounds = L.latLngBounds(L.latLng(-90, -Infinity), L.latLng(90, Infinity));

        this.map = L.map('map', {
            zoomControl: false,
            attributionControl: false,
            minZoom: 2,
            bounceAtZoomLimits: false,
            worldCopyJump: true,
            maxBounds: worldBounds,
            maxBoundsViscosity: 1.0
        });

        L.control.attribution({
            prefix: false,
            position: 'bottomright'
        }).addTo(this.map);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x.png' : '.png'), {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            // Remove the noWrap option
        }).addTo(this.map);

        this.updateInfoBox();
        this.fitToBounds(this.locations);

        this.pixiContainer = new PIXI.ParticleContainer({maxSize: Math.min(this.locations.length, this.maxMarkers), vertices: true});
        this.pixiOverlay = L.pixiOverlay((utils) => {
            const renderer = utils.getRenderer();
            const container = utils.getContainer();
            let markerTexture = renderer.generateTexture(new PIXI.Graphics().beginFill(0x17388e).drawCircle(0, 0, config.markerSize).endFill());
            const project = this.pixiOverlay.utils.latLngToLayerPoint;

            this.pixiContainer.removeChildren();

            const bounds = this.map.getBounds();
            const visibleLocations = this.filteredLocations.filter(loc => 
                this.isLocationVisible(bounds, loc)
            );

            const locationsToRender = visibleLocations.slice(0, this.maxMarkers);
            
            locationsToRender.forEach((loc) => {
                const wrappedLocs = this.getWrappedLocations(loc);
                wrappedLocs.forEach(wrappedLoc => {
                    const markerCoords = project([wrappedLoc.lat, wrappedLoc.lng]);
                    const marker = new PIXI.Sprite(markerTexture);
                    
                    marker.interactiveChildren = false;
                    marker.anchor.set(0.5, 1);
                    marker.position.set(markerCoords.x, markerCoords.y);
    
                    
                    marker.scale.set(this.markerScaleSize(this.map));

                    this.pixiContainer.addChild(marker);
                });
            });
    
            renderer.render(container);
        }, this.pixiContainer, {destroyInteractionManager: true, clearBeforeRender: true});

        this.initialize();

        // Tooltip handler
        this.tooltip = document.getElementById("tooltip");
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

        // this.map.on('drag', () => {
        //     this.map.panInsideBounds(worldBounds, { animate: false });
        // });

        this.map.on('zoom', () => {
            if (this.map.getZoom() < this.map.getMinZoom()) {
                this.map.setZoom(this.map.getMinZoom());
            }
        });
    }

    initialize() {
        this.updateFilterSelect();
        this.applyFilters();
        this.pixiOverlay.redraw();
        this.updateInfoBox();
        // this.fitToBounds();
    }

    applyFilters() {
        this.filteredLocations = this.locations;
        
        this.filterMap.forEach(filter => {
            if(Object.values(filter).some(val => val === undefined || val === null || val === '')) return;
            filter.filter = unformatAttrString(filter.filter);
            this.filteredLocations = this.filterLocations(this.filteredLocations, filter);
        });
    }

    /**
     * Filters the locations based on the given filter, operator, and value.
     * @param {Array} locations - The array of locations to filter.
     * @param {Object} filterObj - The filter object containing filter, operator, and value.
     * @returns {Array} The filtered locations.
     */
    filterLocations(locations, { filter, operator, value }) {
        const parseDate = (dateStr) => {
            if (/^\d{4}-\d{2}$/.test(dateStr)) {
                return new Date(dateStr + '-01');
            }
            return new Date(dateStr);
        };

        const parseTime = (timeStr) => {
            const [hours, minutes, seconds] = timeStr.split(':').map(Number);
            return hours * 3600 + minutes * 60 + (seconds || 0);
        };

        const compareDates = (locDate, filterDate, op) => {
            const locTime = locDate.getTime();
            const filterTime = filterDate.getTime();
            switch(op) {
                case '=': return locTime === filterTime;
                case '!=': return locTime !== filterTime;
                case '>=': return locTime >= filterTime;
                case '<=': return locTime <= filterTime;
                case '>': return locTime > filterTime;
                case '<': return locTime < filterTime;
                default: return true;
            }
        };

        const compareTimes = (locTime, filterTime, op) => {
            switch(op) {
                case '=': return locTime === filterTime;
                case '!=': return locTime !== filterTime;
                case '>=': return locTime >= filterTime;
                case '<=': return locTime <= filterTime;
                case '>': return locTime > filterTime;
                case '<': return locTime < filterTime;
                default: return true;
            }
        };

        return locations.filter(loc => {
            let locValue = loc[filter];
            let parsedValue;
            
            if (filter === 'imageDate') {
                const locDate = parseDate(locValue);
                const filterDate = parseDate(value);
                return compareDates(locDate, filterDate, operator);
            }
            
            if (filter === 'timestamp') {
                const locDate = new Date(locValue * 1000);
                if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(value)) {
                    const locTime = locDate.getHours() * 3600 + locDate.getMinutes() * 60 + locDate.getSeconds();
                    const filterTime = parseTime(value);
                    return compareTimes(locTime, filterTime, operator);
                } else {
                    const filterDate = new Date(value);
                    return compareDates(locDate, filterDate, operator);
                }
            }
            
            if(isNaN(parseFloat(value)) && typeof locValue === 'string'){
                parsedValue = value.toLowerCase();
                locValue = locValue.toLowerCase();
            } else {
                parsedValue = parseFloat(value);
            }

            switch(operator) {
                case '=': return locValue == parsedValue;
                case '!=': return locValue != parsedValue;
                case '>=': return locValue >= parsedValue;
                case '<=': return locValue <= parsedValue;
                case '>': return locValue > parsedValue;
                case '<': return locValue < parsedValue;
                default: return true;
            }
        });
    }

    proximalNode(event, range) {
        const mouseLatLng = this.map.mouseEventToLatLng(event.originalEvent);
        const mousePosition = this.pixiOverlay.utils.latLngToLayerPoint(mouseLatLng);
    
        let closestMarker = null;
        let minDistance = Infinity;
        let nearestLocation = null;
    
        this.pixiContainer.children.forEach((marker, index) => {
            const markerPosition = marker.position;
            const distance = Math.hypot(mousePosition.x - markerPosition.x, mousePosition.y - markerPosition.y);
            
            if (distance < minDistance) {
                minDistance = distance;
                closestMarker = marker;
                nearestLocation = this.filteredLocations[Math.floor(index / 3)]; // Divide by 3 because each location can have up to 3 markers due to wrapping
            }
        });
    
        if (!closestMarker) {
            return { inRange: false, mouseOnMarker: false, nearest: null, dist: null };
        }
    
        const markerRadius = this.markerScaleSize() * config.markerSize;
        const mouseOnMarker = minDistance < markerRadius;
        const inRange = (nearestLocation && minDistance < range);
    
        return { inRange, mouseOnMarker, nearest: nearestLocation, dist: minDistance };
    }

    /**
     * Calculates the marker scale size based on the current zoom level.
     * @returns {number} The marker scale size.
     */
    markerScaleSize(){
        const zoom = this.map.getZoom();
        const zoomFactor = 2 ** (9.5 - zoom);
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
     * Updates the filter select dropdowns with the current map attributes.
     */
    updateFilterSelect() {
        const filterContainer = document.getElementById("filterContainer");

        const filterItems = filterContainer.getElementsByClassName('filter-item');
        this.filterMap = Array.from(filterItems, item => ({
            filter: formatAttrString(item.querySelector('.filter')?.value),
            operator: item.querySelector('.filter-operation')?.value,
            value: item.querySelector('.filter-value')?.innerText
        }));

        const filterSelects = filterContainer.getElementsByClassName('filter');
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

    /**
     * Fits the map to the bounds of the locations.
     */
    fitToBounds(locations) {
        if (locations.length > 0) {
            const bounds = L.latLngBounds(locations.map(loc => [loc.lat, loc.lng]));
            this.map.fitBounds(bounds);
        }
    }

    isLocationVisible(bounds, loc) {
        const wrappedLocs = this.getWrappedLocations(loc);
        return wrappedLocs.some(wrappedLoc => bounds.contains(L.latLng(wrappedLoc.lat, wrappedLoc.lng)));
    }

    getWrappedLocations(loc) {
        const worldWidth = 360;
        const lng = loc.lng;
        const wrappedLocs = [
            { lat: loc.lat, lng: lng },
            { lat: loc.lat, lng: lng + worldWidth },
            { lat: loc.lat, lng: lng - worldWidth }
        ];
        return wrappedLocs;
    }
}