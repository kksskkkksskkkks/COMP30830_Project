// nearby.js — Nearby Station Search Feature
// Depends on: window.map (index.js), window.stationMarkers (index.js addMarkers)

(function () {

    // ── State ──────────────────────────────────────────────────────────────────
    let allStations    = [];
    let liveData       = {};
    let searchMarker   = null;
    let currentResults = [];   // all open stations sorted by distance
    let displayLimit   = 20;
    let activeNumber   = null;

    // Favourites — shared with index.js via window
    window.userFavorites = new Set();

    const DUBLIN_CENTER = { lat: 53.3498, lng: -6.2603 };
    const PAGE_SIZE     = 20;

    // ── Hook into initMap without modifying index.js ───────────────────────────
    const _origInitMap = window.initMap;
    window.initMap = function () {
        _origInitMap();
        initNearby();
    };

    function initNearby() {
        document.getElementById('btn-panel-toggle').addEventListener('click', () => {
            if (window.activeInfoWindow) window.activeInfoWindow.close();
            togglePanel();
        });
        document.getElementById('btn-panel-close').addEventListener('click', closePanel);
        document.getElementById('btn-locate').addEventListener('click', handleLocate);
        document.getElementById('btn-search').addEventListener('click', triggerSearch);

        // Close IW when search box is focused
        document.getElementById('search-input').addEventListener('focus', () => {
            if (window.activeInfoWindow) window.activeInfoWindow.close();
        });

        // Escape key closes IW
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && window.activeInfoWindow) window.activeInfoWindow.close();
        });

        window.map.addListener('click', function (e) {
            if (window.activeInfoWindow) window.activeInfoWindow.close();
            placeOrigin(e.latLng.lat(), e.latLng.lng(), 'Pinned Location');
        });

        window.map.addListener('dragstart', function () {
            if (window.activeInfoWindow) window.activeInfoWindow.close();
            clearSearchPin();
        });

        window.map.addListener('dragend', function () {
            const c = window.map.getCenter();
            runNearbySearch(c.lat(), c.lng());
        });

        initAutocomplete();

        // Use the stations promise from index.js (no duplicate fetch) + live data + favorites
        Promise.all([
            window.stationsReady.then(stations => { allStations = stations || []; }),
            fetch('/api/bikes').then(r => r.json()).then(d => { d.forEach(s => { liveData[s.number] = s; }); window.nearbyLiveData = liveData; }),
            loadFavorites(),
        ]).then(() => {
            addMarkers(allStations);   // markers created after live data is ready — badges show accurate counts
            runNearbySearch(DUBLIN_CENTER.lat, DUBLIN_CENTER.lng);
        }).catch(err => console.error('[nearby] data fetch failed:', err));
    }

    // ── Favourites ─────────────────────────────────────────────────────────────
    function loadFavorites() {
        if (!window.IS_LOGGED_IN) return Promise.resolve();
        return fetch('/auth/favorites')
            .then(r => r.json())
            .then(d => { window.userFavorites = new Set((d.favorites || []).map(f => f.station_number)); })
            .catch(() => {});
    }

    function toggleFavorite(stationNumber, btn) {
        const isFav  = window.userFavorites.has(stationNumber);
        const method = isFav ? 'DELETE' : 'POST';
        const url    = isFav ? `/auth/favorites/${stationNumber}` : '/auth/favorites';
        const opts   = { method };
        if (!isFav) {
            opts.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            opts.body    = `station_number=${stationNumber}`;
        }
        fetch(url, opts)
            .then(r => r.json())
            .then(() => {
                if (isFav) { window.userFavorites.delete(stationNumber); }
                else        { window.userFavorites.add(stationNumber); }
                // Sync all fav buttons for this station (card + IW)
                document.querySelectorAll(`.btn-fav[data-fav-number="${stationNumber}"]`).forEach(b => {
                    b.classList.toggle('fav--active', !isFav);
                });
            })
            .catch(err => console.error('[fav] toggle failed:', err));
    }

    window.toggleFavorite = toggleFavorite;

    // ── Panel open / close / toggle ────────────────────────────────────────────
    function openPanel() {
        document.getElementById('results-panel').classList.remove('hidden');
        const btn = document.getElementById('btn-panel-toggle');
        btn.classList.add('panel-open');
        btn.setAttribute('aria-label', 'Close station list');
        btn.setAttribute('aria-expanded', 'true');
    }

    function closePanel() {
        if (window.activeInfoWindow) window.activeInfoWindow.close();
        document.getElementById('results-panel').classList.add('hidden');
        const btn = document.getElementById('btn-panel-toggle');
        btn.classList.remove('panel-open');
        btn.setAttribute('aria-label', 'Open station list');
        btn.setAttribute('aria-expanded', 'false');
    }

    function togglePanel() {
        const panel = document.getElementById('results-panel');
        panel.classList.contains('hidden') ? openPanel() : closePanel();
    }

    
    // ── photon (OpenStreetMap) address autocomplete ──────────────────────────────────
    function initAutocomplete() {
        const input = document.getElementById('search-input');
        const suggestionsEl = createSuggestionsDropdown();

        const doSearch = debounce(function (q) {
            if (q.length === 0) { hideSuggestions(suggestionsEl); return; }
            // Query when user inputs more than 3 characters
            if (q.length < 3) return;
            fetch(`/api/geocode?q=${encodeURIComponent(q)}`)
                .then(r => r.json())
                .then(results => renderSuggestions(suggestionsEl, results))
                .catch(() => hideSuggestions(suggestionsEl));
        }, 200);

        input.addEventListener('input', () => doSearch(input.value.trim()));

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') { hideSuggestions(suggestionsEl); return; }
            if (e.key === 'Enter') {
                e.preventDefault();
                const first = suggestionsEl.querySelector('li');
                if (first) first.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#search-box-area')) hideSuggestions(suggestionsEl);
        });
    }

    function triggerSearch() {
        const q = document.getElementById('search-input').value.trim();
        if (q.length < 4) return;
        const suggestionsEl = document.getElementById('search-suggestions');
        const first = suggestionsEl && suggestionsEl.querySelector('li');
        if (first) {
            first.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            return;
        }
        fetch(`/api/geocode?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(results => {
                if (results.length === 0) return;
                const primary = results[0].name.split(',')[0];
                document.getElementById('search-input').value = primary;
                placeOrigin(results[0].lat, results[0].lng, primary);
            })
            .catch(() => {});
    }

    function createSuggestionsDropdown() {
        const ul = document.createElement('ul');
        ul.id = 'search-suggestions';
        ul.className = 'search-suggestions hidden';
        document.getElementById('search-box-area').appendChild(ul);
        return ul;
    }

    function renderSuggestions(ul, results) {
        ul.innerHTML = '';
        if (results.length === 0) { ul.classList.add('hidden'); return; }
        results.forEach(r => {
            const li  = document.createElement('li');
            const primary   = r.name.split(',')[0];   // first part as the short label
            li.textContent  = r.name;
            li.addEventListener('mousedown', (e) => {
                e.preventDefault();
                hideSuggestions(ul);
                document.getElementById('search-input').value = primary;
                placeOrigin(r.lat, r.lng, primary);
            });
            ul.appendChild(li);
        });
        ul.classList.remove('hidden');
    }

    function hideSuggestions(ul) {
        ul.classList.add('hidden');
        ul.innerHTML = '';
    }

    function debounce(fn, delay) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // ── Geolocation ────────────────────────────────────────────────────────────
    function handleLocate() {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            pos => placeOrigin(pos.coords.latitude, pos.coords.longitude, 'My Location'),
            err => alert('Could not get your location: ' + err.message)
        );
    }

    // ── Place origin pin ───────────────────────────────────────────────────────
    function placeOrigin(lat, lng, label) {
        if (window.activeInfoWindow) window.activeInfoWindow.close();
        if (searchMarker) {
            searchMarker.position = { lat, lng };
            searchMarker.title    = label;
        } else {
            const pin = document.createElement('div');
            pin.className = 'search-pin';
            pin.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="41" height="57" viewBox="-2 -2 40 52" aria-hidden="true">
                <path d="M18 0C8.06 0 0 8.06 0 18c0 13.5 18 30 18 30S36 31.5 36 18C36 8.06 27.94 0 18 0z" 
                fill="#ff5e5e" stroke="#111111" stroke-width="2.5"/> <circle cx="18" cy="18" r="6" fill="#ffffff"/></svg>`;
            searchMarker = new google.maps.marker.AdvancedMarkerElement({
                position: { lat, lng },
                map: window.map,
                title: label,
                content: pin,
                zIndex: 9999,
            });
        }
        window.map.panTo({ lat, lng });
        runNearbySearch(lat, lng);
    }

    // ── Remove the search pin ─────────────────────────────────────────────────
    function clearSearchPin() {
        if (searchMarker) {
            searchMarker.map = null;
            searchMarker = null;
        }
    }
    window.clearSearchPin = clearSearchPin;

    // ── Core search: filter open, sort by distance, page ──────────────────────
    function runNearbySearch(originLat, originLng) {
        displayLimit   = PAGE_SIZE;
        currentResults = allStations
            .map(s => ({
                ...s,
                live: liveData[s.number] || {},
                distance: haversineKm(originLat, originLng, s.lat, s.lng),
            }))
            .filter(s => (s.live.status || '').toUpperCase() === 'OPEN')
            .sort((a, b) => a.distance - b.distance);

        renderPanel(currentResults.slice(0, displayLimit));
        updateMapOverlay(currentResults.slice(0, displayLimit));
    }

    // ── Haversine distance (km) ────────────────────────────────────────────────
    function haversineKm(lat1, lng1, lat2, lng2) {
        const R    = 6371;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a    =
            Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    // ── Render panel cards ─────────────────────────────────────────────────────
    function renderPanel(stations) {
        const list = document.getElementById('station-list');
        list.innerHTML = '';

        if (stations.length === 0) {
            const li = document.createElement('li');
            li.className = 'no-results';
            li.textContent = 'No open stations found nearby.';
            list.appendChild(li);
        } else {
            stations.forEach(s => {
                const bikes  = s.live.available_bikes           !== undefined ? s.live.available_bikes           : '–';
                const stands = s.live.available_bike_stands     !== undefined ? s.live.available_bike_stands     : '–';

                const isFav  = window.IS_LOGGED_IN && window.userFavorites.has(s.number);
                const favBtn = window.IS_LOGGED_IN
                    ? `<button class="btn-fav${isFav ? ' fav--active' : ''}"
                               data-fav-number="${s.number}"
                               aria-label="Toggle favourite">&#9829;</button>`
                    : '';

                const li = document.createElement('li');
                li.className = 'station-card';
                li.dataset.number = s.number;
                li.innerHTML = `
                    <div class="sc-name-row" style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.4rem;">
                        <div class="sc-name">${s.name}</div>
                        ${favBtn}
                    </div>
                    <div class="sc-row">
                        <span class="sc-distance">${s.distance.toFixed(2)} km away</span>
                        <span class="sc-stat"><img src="/static/bike_icon.svg" class="sc-icon" alt="Bike"> ${bikes}</span>
                        <span class="sc-stat"><img src="/static/parking_icon.png" class="sc-icon" alt="Parking"> ${stands}</span>
                    </div>
                `;

                // Fav button click — don't propagate to card
                if (window.IS_LOGGED_IN) {
                    li.querySelector('.btn-fav').addEventListener('click', (e) => {
                        e.stopPropagation();
                        toggleFavorite(s.number, e.currentTarget);
                    });
                }

                li.addEventListener('click', () => {
                    clearSearchPin();
                    window.map.panTo({ lat: s.lat, lng: s.lng });
                    window.map.setZoom(16);
                    setActive(s.number);
                    const marker = (window.stationMarkers || {})[s.number];
                    if (marker) google.maps.event.trigger(marker, 'click');
                });

                li.addEventListener('mouseenter', () => setActive(s.number));
                li.addEventListener('mouseleave', clearActive);

                list.appendChild(li);
            });

            // "Show more" only if more results exist
            if (displayLimit < currentResults.length) {
                const li = document.createElement('li');
                li.className = 'show-more-item';
                li.innerHTML = '<button class="btn-show-more">Show more</button>';
                li.querySelector('button').addEventListener('click', () => {
                    if (window.activeInfoWindow) window.activeInfoWindow.close();
                    displayLimit += PAGE_SIZE;
                    const next = currentResults.slice(0, displayLimit);
                    renderPanel(next);
                    updateMapOverlay(next);
                });
                list.appendChild(li);
            }
        }

        openPanel();
    }

    // ── Map overlay: dim markers not in current display set ────────────────────
    function updateMapOverlay(displayedStations) {
        const shown   = new Set(displayedStations.map(s => s.number));
        const markers = window.stationMarkers || {};
        Object.keys(markers).forEach(num => {
            markers[num].content.style.display = shown.has(parseInt(num)) ? '' : 'none';
        });
    }

    // ── Card marker highlight ────────────────────────────────────────────────
    function setActive(number) {
        clearActive();
        activeNumber = number;

        const card = document.querySelector(`.station-card[data-number="${number}"]`);
        if (card) {
            card.classList.add('active');
            card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }

        const marker = (window.stationMarkers || {})[number];
        if (marker) {
            marker.content.classList.add('station-badge--active');
            marker.zIndex = 500;
        }
    }

    function clearActive() {
        if (activeNumber === null) return;

        const card = document.querySelector(`.station-card[data-number="${activeNumber}"]`);
        if (card) card.classList.remove('active');

        const marker = (window.stationMarkers || {})[activeNumber];
        if (marker) {
            marker.content.classList.remove('station-badge--active');
            marker.zIndex = null;
        }
        activeNumber = null;
    }

    // Expose active state controls to index.js
    window.nearbySetActive   = setActive;
    window.nearbyClearActive = clearActive;

})();
