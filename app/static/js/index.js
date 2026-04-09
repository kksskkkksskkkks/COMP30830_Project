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


    getStations().then(stations => {
        if (stations) {
            addMarkers(stations);
        }
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
        const live   = (window.nearbyLiveData || {})[station.number] || {};
        const bikes  = live.available_bikes       !== undefined ? live.available_bikes       : '–';
        const stands = live.available_bike_stands !== undefined ? live.available_bike_stands : '–';

        const badge = document.createElement('div');
        badge.className = 'station-badge';
        badge.innerHTML = `<span>🚲 ${bikes}</span><span class="badge-divider">|</span><span>🅿️ ${stands}</span>`;

        const marker = new google.maps.marker.AdvancedMarkerElement({
            position: { lat: station.lat, lng: station.lng },
            map: map,
            title: station.name,
            content: badge,
        });

        window.stationMarkers[station.number] = marker;

        // Click — open info window with 24h prediction charts
        marker.addListener("click", () => {
            const sid    = station.number;
            const ld     = (window.nearbyLiveData || {})[sid] || {};
            const bikes2  = ld.available_bikes       !== undefined ? ld.available_bikes       : 'N/A';
            const stands2 = ld.available_bike_stands !== undefined ? ld.available_bike_stands : 'N/A';

            if (window.nearbySetActive) window.nearbySetActive(sid);

            const isFav = window.IS_LOGGED_IN && window.userFavorites && window.userFavorites.has(station.number);
            const favBtn = window.IS_LOGGED_IN
                ? `<button class="btn-fav${isFav ? ' fav--active' : ''}"
                          data-fav-number="${station.number}"
                          onclick="window.toggleFavorite(${station.number}, this)"
                          aria-label="Toggle favourite">&#9829;</button>`
                : '';

            const content = `
                <div style="min-width: 280px;">
                    <div class="iw-header">
                        <div class="iw-title">${station.name}</div>
                        <button class="iw-close" onclick="window.activeInfoWindow.close()" aria-label="Close">&#x2715;</button>
                    </div>
                    <div class="iw-stats">
                        🚲 <strong>${bikes2}</strong> bikes &nbsp;|&nbsp; 🅿️ <strong>${stands2}</strong> stands
                    </div>
                    <div id="bike_pred_${sid}" class="iw-chart" style="background: #fdfaf6; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; color: #666;">
                        Loading bike predictions...
                    </div>
                    <div id="stand_pred_${sid}" class="iw-chart" style="margin-top: 10px; background: #fdfaf6; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; color: #666;">
                        Loading stand predictions...
                    </div>
                </div>
            `;

            window.activeInfoWindow.setContent(content);
            window.activeInfoWindow.open(map, marker);

            google.maps.event.addListenerOnce(window.activeInfoWindow, 'domready', () => {
                // Focus/Pan adjustment
                requestAnimationFrame(() => {
                    const iw = document.querySelector('.gm-style-iw-a');
                    const searchFloat = document.getElementById('search-float');
                    if (iw && searchFloat) {
                        const iwTop = iw.getBoundingClientRect().top;
                        const searchBottom = searchFloat.getBoundingClientRect().bottom;
                        const gap = 16;
                        if (iwTop < searchBottom + gap) {
                            window.map.panBy(0, -(searchBottom + gap - iwTop));
                        }
                    }
                });

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
                            drawPredictionChart(res.chart_data, `bike_pred_${sid}`, "Predicted Available Bikes", "#4285F4");
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
                            drawPredictionChart(res.chart_data, `stand_pred_${sid}`, "Predicted Empty Stands", "#EA4335");
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

        // Hover — open info window (same as click)
        marker.addListener("mouseover", () => {
            google.maps.event.trigger(marker, 'click');
        });
    }
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
        hAxis: { format: 'HH:mm', gridlines: { count: 3 }, textStyle: { fontSize: 10 } },
        vAxis: { minValue: 0, textStyle: { fontSize: 10 } },
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
    fetch("/db/weather/current")
    .then((response) => response.json())
    .then((data) => displayWeather(data))
    .catch((error) => console.error("Error fetching weather data:", error));
}

function displayWeather(data) {
    console.log("Full data received:", data);

    if (!data || !data.current) {
        console.error("error data structure or fail fetch data");
        document.getElementById("weather").innerHTML = "Weather data unavailable";
        return;
    }

    const weatherDiv = document.getElementById("weather");
    weatherDiv.innerHTML = `
        <div style="font-weight: bold;">Dublin Weather</div>
        <div style="font-size: 1.2em;">${Math.round(data.current.feels_like)}°C</div>
        <div style="text-transform: capitalize;">${data.current.weather[0].description}</div>
    `;
}
