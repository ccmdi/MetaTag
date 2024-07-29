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
        this.locations = json.customCoordinates;
        this.filteredLocations = this.locations;
        // this.markers = [];

        this.map = L.map('map', {zoomControl: false});
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}' + (L.Browser.retina ? '@2x.png' : '.png'), {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(this.map);

        this.pixiContainer = new PIXI.ParticleContainer({maxSize: this.locations.length, vertices: true});
        this.pixiOverlay = L.pixiOverlay((utils) => {
            const renderer = utils.getRenderer();
            const container = utils.getContainer();
            let markerTexture = renderer.generateTexture(new PIXI.Graphics().beginFill(0x17388e).drawCircle(0, 0, config.markerSize).endFill());
            const project = this.pixiOverlay.utils.latLngToLayerPoint;

            this.pixiContainer.removeChildren();
            
            this.filteredLocations.forEach((loc) => {
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
        
        //Set initial view
        let mapGroup = new L.featureGroup(this.filteredLocations.map((loc) => L.marker([loc.lat, loc.lng])));
        this.map.fitBounds(mapGroup.getBounds());

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
    }

    initialize() {
        this.filteredLocations = this.locations;
        this.filterMap.forEach((filter) => {
            this.filteredLocations = this.filter(this.filteredLocations, filter);
        });
        console.log(this.filteredLocations);
        this.tree = new kdTree(this.filteredLocations, distance, ['lat','lng']);
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
        const zoomFactor = 2 ** (9 - zoom);
        return zoomFactor;
    }
}