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
        mapId: 'DEMO_MAP_ID',
        gestureHandling: 'greedy',
    });

    // Expose stations promise — nearby.js uses it to avoid a duplicate fetch
    window.stationsReady = getStations();
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
        const bikes  = live.available_bikes           !== undefined ? live.available_bikes           : '–';
        const stands = live.available_bike_stands     !== undefined ? live.available_bike_stands     : '–';

        // Mini badge shown on the map
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

        // Click — open info window with chart
        marker.addListener("click", () => {
            const ld     = (window.nearbyLiveData || {})[station.number] || {};
            const bikes2  = ld.available_bikes       !== undefined ? ld.available_bikes       : 'N/A';
            const stands2 = ld.available_bike_stands !== undefined ? ld.available_bike_stands : 'N/A';

            if (window.nearbySetActive) window.nearbySetActive(station.number);

            const content = `
                <div>
                    <div class="iw-header">
                        <div class="iw-title">${station.name}</div>
                        <button class="iw-close" onclick="window.activeInfoWindow.close()" aria-label="Close">&#x2715;</button>
                    </div>
                    <div class="iw-stats">🚲 <strong>${bikes2}</strong> bikes &nbsp;|&nbsp; 🅿️ <strong>${stands2}</strong> stands</div>
                    <div id="chart_div_${station.number}" class="iw-chart"></div>
                </div>
            `;

            window.activeInfoWindow.setContent(content);
            window.activeInfoWindow.open(map, marker);

            google.maps.event.addListenerOnce(window.activeInfoWindow, 'domready', () => {
                // Pan map so IW clears the search bar
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

                fetch(`/db/available/${station.number}`)
                    .then((response) => response.json())
                    .then((data) => {
                        google.charts.setOnLoadCallback(() => drawChart(data.available, station.number));
                    })
                    .catch((error) => {
                        console.error(`Error fetching data for station ${station.number}:`, error);
                    });
            });
        });

        // Hover — open info window (same as click)
        marker.addListener("mouseover", () => {
            google.maps.event.trigger(marker, 'click');
        });
    }
}

// Function to draw the chart using Google Charts
function drawChart(data, stationId) {
    const chartData = new google.visualization.DataTable();

    chartData.addColumn('datetime', 'Time');
    chartData.addColumn('number', 'Available Bikes');

    data.forEach((entry) => {
        chartData.addRow([
            new Date(entry.last_update),
            entry.available_bikes,
        ]);
    });

    const options = {
        title: `Available Bikes at Station ${stationId}`,
        hAxis: { title: 'Time', format: 'HH:mm' },
        vAxis: { title: 'Available Bikes' },
        curveType: 'function',
        legend: { position: 'bottom' },
        width: 280,
        height: 150,
    };

    const chart = new google.visualization.LineChart(
        document.getElementById(`chart_div_${stationId}`)
    );

    chart.draw(chartData, options);
}


// Get current weather
function getWeather() {
    fetch("/db/weather/current")
    .then((response) => response.json())
    .then((data) => displayWeather(data))
    .catch((error) => console.error("Error fetching weather data:", error));
}

function displayWeather(data) {
    console.log("This is what I received:", data);
    console.log("This is what I received:", data.current.temp);
    const weatherDiv = document.getElementById("weather");
    weatherDiv.innerHTML = `
        <div style="font-weight: bold;">Dublin Weather</div>
        <div style="font-size: 1.2em;">${Math.round(data.current.feels_like)}°C</div>
        <div style="text-transform: capitalize;">${data.current.weather[0].description}</div>
    `;
}
