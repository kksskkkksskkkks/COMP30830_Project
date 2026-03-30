// Initialize and add the map
function initMap() {
    const dublin = { lat: 53.35014, lng: -6.266155 };

    // The map, centered at Dublin
    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 14,
        center: dublin,
    });

    getStations();
    getWeather();
}

var map = null;
window.initMap = initMap;


function getStations() {
    fetch("/db/stations")
    .then((response) => {
        return response.json()
    })
    .then((data) => {

        console.log("fetch response", typeof data);
        addMarkers(data.stations);
    })
    .catch((error) => {
        console.log("Error fetching stations data: ", error);
    })
}

function addMarkers(stations) {
    console.log(stations); 

    for (const station of stations) {
        // Create a marker for each station
        const marker = new google.maps.Marker({
            position: {
                lat: station.lat, // according to station sql
                lng: station.lng, // according to station sql
            },
            map: map,
            title: station.name,
            station_number: station.number,
            icon: 'https://icons.iconarchive.com/icons/aha-soft/transport/48/bike-icon.png',
        });
        window.stationMarkers = window.stationMarkers || {};
        window.stationMarkers[station.number] = marker;

        // Create an empty infowindow
        const infoWindow = new google.maps.InfoWindow({});

        // Add a click listener to the marker to show the info window
        marker.addListener("click", () => {
            // Define container for the chart
            const chartContainer = document.createElement('div');
            chartContainer.style.width = '300px';
            chartContainer.style.height = '200px';

            // Info window content (including chart div placeholder with this id)
            const content = `
                <div>
                    <h3>${station.number}</h3>
                    <p><strong>Address:</strong> ${station.number || "N/A"}</p>
                    <p><strong>Available Bike Stands:</strong> ${station.available_bike_stands || "N/A"}</p>
                    <div id="chart_div_${station.number}" style="width: 300px; height: 200px;"></div>
                </div>
            `;

            // Set the content
            infoWindow.setContent(content);

            // Open the window
            infoWindow.open(map, marker);

            // ADD CHART CODE

            // Fetch the station-specific data and draw the chart
            fetch(`/db/available/${station.number}`)
                .then((response) => response.json())
                .then((data) => {
                    // Load Google Charts library
                    google.charts.load('current', { packages: ['corechart'] });

                    // When the library is ready, draw the chart (calling the function drawChart)
                    google.charts.setOnLoadCallback(() => drawChart(data, station.number));
                })
                .catch((error) => {
                    console.error(`Error fetching data for station ${station.number}:`, error);
                });
        });
    }
}

// Function to draw the chart using Google Charts
function drawChart(data, stationId) {
    const chartData = new google.visualization.DataTable();

    // Define columns
    chartData.addColumn('datetime', 'Time'); // x-axis (Date/Time)
    chartData.addColumn('number', 'Available Bikes'); // y-axis (Bikes)

    // Populate chart rows with fetched data
    data.forEach((entry) => {
        chartData.addRow([
            new Date(entry.last_update), // Convert timestamp to Date
            entry.available_bikes,      // Bikes count
        ]);
    });

    // Chart options
    const options = {
        title: `Available Bikes at Station ${stationId}`,
        hAxis: {
            title: 'Time',
            format: 'HH:mm', // Format time as hours and minutes
        },
        vAxis: {
            title: 'Available Bikes',
        },
        curveType: 'function', // Smooth line
        legend: { position: 'bottom' },
        width: 400,
        height: 250,
    };

    // Draw the chart in the placeholder div
    const chart = new google.visualization.LineChart(
        document.getElementById(`chart_div_${stationId}`)
    );

    chart.draw(chartData, options);
}


// Get current weather
function getWeather() {
    fetch("/db/weather/current")
    .then((response) => {
        return response.json()
    })
    .then((data) => {

        console.log("fetch response", typeof data);

        displayWeather(data);
    })
    .catch((error) => {
        console.log("Error fetching weather data: ", error);
    })
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