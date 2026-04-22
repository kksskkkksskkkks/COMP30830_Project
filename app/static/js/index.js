// Read config injected by the template
const _cfg = document.getElementById('app-config').dataset;
window.IS_LOGGED_IN = _cfg.loggedIn === 'true';
window.MAP_ID       = _cfg.mapId;

// Initialize and add the map
function initMap() {
    const dublin = { lat: 53.35014, lng: -6.266155 };

    window.activeInfoWindow = new google.maps.InfoWindow({});
    window.activeInfoWindow.addListener('closeclick', () => {
        if (window.nearbyClearActive) window.nearbyClearActive();
    });

    // Load Charts library once — ready before any marker is clicked
    google.charts.load('current', { packages: ['corechart'] });

    // The map, centered at Dublin
    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 14,
        center: dublin,
        mapId: window.MAP_ID,
        gestureHandling: 'greedy',
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        rotateControl: false,
        scaleControl: false,
        clickableIcons: false,
    });

    // Expose stations promise — nearby.js uses it to avoid a duplicate fetch
    window.stationsReady = getStations();

    // Update pin sizes when user zooms
    map.addListener('zoom_changed', () => {
        const mode = getBadgeMode(map.getZoom());
        Object.values(window.stationMarkers || {}).forEach(m => applyPinMode(m.content, mode));
    });

    getWeather();
}

var map = null;
window.initMap = initMap;


function getStations() {
    return fetch("/db/stations")
    .then((response) => response.json())
    .then((data) => data.stations)
    .catch((error) => console.error("Error fetching stations data:", error));
}

function addMarkers(stations) {
    window.stationMarkers = window.stationMarkers || {};

    for (const station of stations) {
        // Remove any existing markers for this station before recreating
        if (window.stationMarkers[station.number]) {
            window.stationMarkers[station.number].map = null;
        }

        const live   = (window.nearbyLiveData || {})[station.number] || {};
        const status = live.status || '';
        const bikes  = live.available_bikes       !== undefined ? live.available_bikes       : null;
        const stands = live.available_bike_stands !== undefined ? live.available_bike_stands : null;

        const pinEl = document.createElement('div');
        pinEl.className = 'station-pin';
        pinEl.dataset.bikes  = bikes  !== null ? bikes  : '';
        pinEl.dataset.stands = stands !== null ? stands : '';
        pinEl.dataset.status = status;
        pinEl.dataset.avail  = getPinAvail(status, bikes, stands);
        pinEl.innerHTML = buildPinHTML(bikes);
        applyPinMode(pinEl, getBadgeMode(map.getZoom()));

        const marker = new google.maps.marker.AdvancedMarkerElement({
            position: { lat: station.lat, lng: station.lng },
            map: map,
            title: station.name,
            content: pinEl,
        });

        window.stationMarkers[station.number] = marker;

        // Click — open info window with 24h prediction charts
        marker.addListener("click", () => {
            const sid    = station.number;
            const ld     = (window.nearbyLiveData || {})[sid] || {};
            const bikes2  = ld.available_bikes       !== undefined ? ld.available_bikes       : 'N/A';
            const stands2 = ld.available_bike_stands !== undefined ? ld.available_bike_stands : 'N/A';

            const content = `
                <div style="min-width: 280px;">
                    <div class="iw-header">
                        <div class="iw-title">${station.name}</div>
                        <button class="iw-close" onclick="window.activeInfoWindow.close()" aria-label="Close">&#x2715;</button>
                    </div>
                    <div class="iw-stats">
                        <img src="/static/bike_icon.svg" class="stat-icon" alt="Bike"> <strong>${bikes2}</strong> bikes &nbsp;|&nbsp; <img src="/static/parking_icon.png" class="stat-icon" alt="Parking"> <strong>${stands2}</strong> stands
                    </div>
                    <div id="bike_pred_${sid}" class="iw-chart" style="background: #fdfaf6; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; color: #666;">
                        Loading bike predictions...
                    </div>
                    <div id="stand_pred_${sid}" class="iw-chart" style="margin-top: 10px; background: #fdfaf6; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; color: #666;">
                        Loading stand predictions...
                    </div>
                    ${window.IS_LOGGED_IN
                        ? `<div style="margin-top: 10px; text-align: center;">
                               <a href="/bike/plot?station_id=${sid}" target="_blank"
                                  class="btn btn-primary"
                                  style="font-size: 0.68rem; padding: 0.3rem 0.75rem; display: inline-block;">
                                   View Next 24H Estimation ↗
                               </a>
                           </div>`
                        : `<div style="margin-top: 10px; padding-top: 8px; border-top: 3px solid #111; font-size: 0.78rem; font-weight: 600; text-align: center; color: #555;">
                               <a href="/auth/login" style="color: var(--primary); font-weight: 700;">Log in</a> to see 24h availability estimation
                           </div>`
                    }
                </div>
            `;

            window.activeInfoWindow.setContent(content);
            window.activeInfoWindow.open(map, marker);

            google.maps.event.addListenerOnce(window.activeInfoWindow, 'domready', () => {
                // Get current local time for backend (YYYY-MM-DD HH:MM:SS)
                const now = new Date();
                const d = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
                const t = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0') + ':' + String(now.getSeconds()).padStart(2, '0');

                console.log(`[ML] Fetching predictions for station ${sid} at ${d} ${t}`);

                // 1. Fetch Bike Prediction
                fetch(`/predict/bike/24h?station_id=${sid}&date=${d}&time=${t}`)
                    .then(r => r.json())
                    .then(res => {
                        if (res.status === "success" && res.chart_data) {
                            const slicedBike = {
                                ...res.chart_data,
                                labels: res.chart_data.labels.slice(0, 5),
                                data_available_bikes: (res.chart_data.data_available_bikes || []).slice(0, 5)
                            };
                            drawPredictionChart(slicedBike, `bike_pred_${sid}`, "Estimated Available Bikes", "#4285F4");
                        } else {
                            document.getElementById(`bike_pred_${sid}`).innerText = "Bike data unavailable";
                            console.warn("Bike ML error:", res);
                        }
                    })
                    .catch(err => {
                        document.getElementById(`bike_pred_${sid}`).innerText = "Fetch error";
                        console.error("Bike fetch failed:", err);
                    });

                // 2. Fetch Stand Prediction
                fetch(`/predict/stand/24h?station_id=${sid}&date=${d}&time=${t}`)
                    .then(r => r.json())
                    .then(res => {
                        if (res.status === "success" && res.chart_data) {
                            const slicedStand = {
                                ...res.chart_data,
                                labels: res.chart_data.labels.slice(0, 5),
                                data_empty_stands: (res.chart_data.data_empty_stands || []).slice(0, 5)
                            };
                            drawPredictionChart(slicedStand, `stand_pred_${sid}`, "Estimated Available Stands", "#EA4335");
                        } else {
                            document.getElementById(`stand_pred_${sid}`).innerText = "Stand data unavailable";
                            console.warn("Stand ML error:", res);
                        }
                    })
                    .catch(err => {
                        document.getElementById(`stand_pred_${sid}`).innerText = "Fetch error";
                        console.error("Stand fetch failed:", err);
                    });
            });
        });

        // Hover — move to the top
        pinEl.addEventListener("mouseenter", () => {
            marker.zIndex = 9999;
        });

        pinEl.addEventListener("mouseleave", () => {
            if (!pinEl.classList.contains('station-badge--active')) {
                marker.zIndex = null;
            }
        });
    }
}


// ── Pin marker helpers ────────────────────────────────────────────────────────

function getPinAvail(status, bikes, stands) {
    if (!status || status.toUpperCase() !== 'OPEN') return 'closed';
    if (bikes === null) return 'unknown';
    if (stands === 0)   return 'full';   // no empty docks
    if (bikes === 0)    return 'empty';  // no bikes
    return 'good';
}

function buildPinHTML(bikes) {
    const label = bikes !== null ? bikes : '–';
    return `<svg class="pin-svg" viewBox="0 0 40 52" xmlns="http://www.w3.org/2000/svg"><path d="M20 2 C10 2 2 10 2 20 C2 32 20 50 20 50 C20 50 38 32 38 20 C38 10 30 2 20 2 Z"/></svg><span class="pin-label">${label}</span>`;
}

function getBadgeMode(zoom) {
    if (zoom >= 15) return 'full';
    if (zoom >= 13) return 'compact';
    return 'dot';
}

function applyPinMode(pinEl, mode) {
    pinEl.classList.remove('pin--full', 'pin--compact', 'pin--dot');
    pinEl.classList.add(`pin--${mode}`);
    const isDot = mode === 'dot';
    const svg   = pinEl.querySelector('.pin-svg');
    const label = pinEl.querySelector('.pin-label');
    if (svg)   svg.style.display   = isDot ? 'none' : '';
    if (label) label.style.display = isDot ? 'none' : '';
}

// Draw prediction chart from ML backend
function drawPredictionChart(chartData, containerId, label, color) {
    if (!chartData || !chartData.labels) return;

    const dataTable = new google.visualization.DataTable();
    dataTable.addColumn('datetime', 'Time');
    dataTable.addColumn('number', label);

    const labels = chartData.labels;
    // data_available_bikes for bike route, data_empty_stands for stand route
    const values = chartData.data_available_bikes || chartData.data_empty_stands || [];

    if (labels.length === 0) {
        document.getElementById(containerId).innerText = "No data available";
        return;
    }

    labels.forEach((ts, i) => {
        dataTable.addRow([new Date(ts), values[i] || 0]);
    });

    const options = {
        title: label,
        titleTextStyle: { fontSize: 13, bold: true },
        hAxis: { format: 'HH:mm', gridlines: { count: 3 }, textStyle: { fontSize: 10 } },
        vAxis: { minValue: 0, textStyle: { fontSize: 12 } },
        colors: [color],
        legend: 'none',
        width: 280,
        height: 140,
        chartArea: { width: '80%', height: '70%' },
        backgroundColor: 'transparent'
    };

    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear loading text
    container.innerHTML = '';

    const chart = new google.visualization.LineChart(container);
    chart.draw(dataTable, options);
}


// Get current weather
function getWeather() {
    fetch("/api/weather")
    .then((response) => response.json())
    .then((data) => displayWeather(data))
    .catch((error) => console.error("Error fetching weather data:", error));
}

function displayWeather(data) {
    console.log("Full data received:", data);

    if (!data || !data.main) {
        console.error("error data structure or fail fetch data");
        document.getElementById("weather").innerHTML = "Weather data unavailable";
        return;
    }

    const weatherDiv = document.getElementById("weather");
    weatherDiv.innerHTML = `
    <div style="font-weight: bold;">Dublin Weather</div>
    <div style="display: flex; align-items: center; gap: 0px; line-height: 1;">
        <img src="https://openweathermap.org/img/wn/${data.weather[0].icon}@2x.png" style="width: 50px; height: 50px;">
        <span style="font-size: 1.2em;">${Math.round(data.main.temp)}°C</span>
    </div>
    <div style="text-transform: capitalize;">${data.weather[0].description}</div>
`;
}
