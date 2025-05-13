/**
 * Global Map Visualization JavaScript
 */

// Global variables
let map = null;
let backendMarkers = [];
let pathLayer = null;
let userMarker = null;
let selectedRegion = 'us-east-1';

/**
 * Initialize the map page
 */
function initMap() {
    // Initialize the Leaflet map
    initializeLeafletMap();
    
    // Load backend data
    loadBackendData();
    
    // Set up event listeners
    document.getElementById('view-all-btn').addEventListener('click', () => filterMapMarkers('all'));
    document.getElementById('view-healthy-btn').addEventListener('click', () => filterMapMarkers('healthy'));
    document.getElementById('view-degraded-btn').addEventListener('click', () => filterMapMarkers('degraded'));
    document.getElementById('simulate-fluctuation-btn').addEventListener('click', simulateFluctuation);
    document.getElementById('user-region').addEventListener('change', updateUserRegion);
    document.getElementById('show-optimal-paths-btn').addEventListener('click', showOptimalPaths);
    
    // Initialize the routing simulation
    initializeRoutingSimulation();
}

/**
 * Initialize Leaflet map
 */
function initializeLeafletMap() {
    // Create map instance
    map = L.map('global-map', {
        center: [20, 0],
        zoom: 2,
        minZoom: 2,
        maxZoom: 7,
        maxBounds: [[-85, -180], [85, 180]]
    });
    
    // Add tile layer (map imagery)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    // Add path layer for routing visualization
    pathLayer = L.layerGroup().addTo(map);
    
    // Create marker for user region
    const userCoords = getRegionCoordinates(selectedRegion);
    userMarker = L.marker([userCoords.lat, userCoords.lng], {
        icon: L.divIcon({
            className: 'user-marker',
            html: '<div style="background-color:#3498db; width:15px; height:15px; border-radius:50%; border:2px solid white; box-shadow:0 0 5px rgba(0,0,0,0.3);"></div>',
            iconSize: [15, 15],
            iconAnchor: [7, 7]
        })
    }).addTo(map);
    
    // Add tooltip to user marker
    userMarker.bindTooltip(`User Region: ${selectedRegion}`, {
        permanent: false,
        direction: 'top',
        offset: [0, -10]
    });
}

/**
 * Load backend data and create markers
 */
async function loadBackendData() {
    try {
        // Fetch backend data
        const backends = await fetchBackends();
        
        // Create markers for each backend
        createBackendMarkers(backends);
        
        // Update region statistics table
        updateRegionStatsTable();
        
        // Update backends table
        updateBackendDetailsTable(backends);
        
    } catch (error) {
        console.error('Error loading backend data:', error);
    }
}

/**
 * Create map markers for backends
 * @param {Array} backends - Array of backend objects
 */
function createBackendMarkers(backends) {
    // Clear existing markers
    backendMarkers.forEach(marker => marker.remove());
    backendMarkers = [];
    
    // Group backends by region for clustering
    const backendsByRegion = {};
    
    backends.forEach(backend => {
        if (!backendsByRegion[backend.region]) {
            backendsByRegion[backend.region] = [];
        }
        backendsByRegion[backend.region].push(backend);
    });
    
    // Create markers for each region
    for (const [region, regionBackends] of Object.entries(backendsByRegion)) {
        const regionCoords = getRegionCoordinates(region);
        
        // Count backends by status
        const healthyCounts = regionBackends.filter(b => b.status === 'healthy').length;
        const degradedCounts = regionBackends.filter(b => b.status === 'degraded').length;
        const downCounts = regionBackends.filter(b => b.status === 'down').length;
        
        // Group backends by chip type
        const chipTypes = {};
        regionBackends.forEach(backend => {
            if (!chipTypes[backend.chip_type]) {
                chipTypes[backend.chip_type] = [];
            }
            chipTypes[backend.chip_type].push(backend);
        });
        
        // Create marker
        const marker = L.marker([regionCoords.lat, regionCoords.lng], {
            icon: L.divIcon({
                className: 'region-marker',
                html: `<div class="region-marker-container" style="background-color:#2c3e50; color:white; border-radius:50%; width:40px; height:40px; display:flex; align-items:center; justify-content:center; border:2px solid white; box-shadow:0 0 5px rgba(0,0,0,0.3); font-weight:bold;">${regionBackends.length}</div>`,
                iconSize: [40, 40],
                iconAnchor: [20, 20]
            })
        }).addTo(map);
        
        // Create popup content
        let popupContent = `
            <div class="popup-title">${region}</div>
            <div class="popup-info">Total Backends: ${regionBackends.length}</div>
            <div class="popup-info">Healthy: <span style="color:#2ecc71">${healthyCounts}</span>, Degraded: <span style="color:#f39c12">${degradedCounts}</span>, Down: <span style="color:#e74c3c">${downCounts}</span></div>
            <div class="popup-title" style="margin-top:8px">Hardware Types:</div>
        `;
        
        for (const [chipType, chipBackends] of Object.entries(chipTypes)) {
            popupContent += `<div class="popup-info">${chipType}: ${chipBackends.length}</div>`;
        }
        
        popupContent += `<div class="popup-title" style="margin-top:8px">Compliance:</div>`;
        
        // Get unique compliance tags in this region
        const complianceTags = new Set();
        regionBackends.forEach(backend => {
            backend.compliance_tags.forEach(tag => complianceTags.add(tag));
        });
        
        popupContent += `<div style="margin-top:5px">`;
        Array.from(complianceTags).forEach(tag => {
            popupContent += `<span class="popup-badge compliance-badge">${tag}</span>`;
        });
        popupContent += `</div>`;
        
        // Get unique models in this region
        const models = new Set();
        regionBackends.forEach(backend => {
            backend.supported_models.forEach(model => models.add(model));
        });
        
        popupContent += `<div class="popup-title" style="margin-top:8px">Supported Models:</div>`;
        popupContent += `<div style="margin-top:5px">`;
        Array.from(models).forEach(model => {
            popupContent += `<span class="popup-badge model-popup-badge">${model}</span>`;
        });
        popupContent += `</div>`;
        
        // Add popup to marker
        marker.bindPopup(popupContent, {
            maxWidth: 300
        });
        
        // Store region info with marker
        marker.region = region;
        marker.backends = regionBackends;
        
        // Add to markers array
        backendMarkers.push(marker);
    }
}

/**
 * Filter map markers based on status
 * @param {string} filter - Filter to apply ('all', 'healthy', 'degraded', or 'down')
 */
function filterMapMarkers(filter) {
    // Update active button
    document.querySelectorAll('.map-controls .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`view-${filter}-btn`).classList.add('active');
    
    // Filter backends
    const backends = globalBackends.filter(backend => {
        if (filter === 'all') return true;
        return backend.status === filter;
    });
    
    // Re-create markers
    createBackendMarkers(backends);
}

/**
 * Simulate backend fluctuation
 */
async function simulateFluctuation() {
    try {
        const response = await fetch('/api/simulate-fluctuation', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Reload backend data to reflect changes
            await loadBackendData();
            
            // Show toast notification
            showToast('Backend fluctuation simulated', 'Random backend status changes have been applied.');
        }
    } catch (error) {
        console.error('Error simulating fluctuation:', error);
    }
}

/**
 * Update region statistics table
 */
async function updateRegionStatsTable() {
    try {
        const response = await fetch('/api/region-stats');
        const stats = await response.json();
        
        // Get table body
        const tableBody = document.getElementById('region-stats-table').querySelector('tbody');
        tableBody.innerHTML = '';
        
        // Add rows for each region
        for (const [region, regionStats] of Object.entries(stats)) {
            const row = document.createElement('tr');
            
            // Region name
            const regionCell = document.createElement('td');
            regionCell.textContent = region;
            row.appendChild(regionCell);
            
            // Backend count
            const countCell = document.createElement('td');
            countCell.textContent = regionStats.backend_count;
            row.appendChild(countCell);
            
            // Health status
            const healthCell = document.createElement('td');
            const healthPct = regionStats.backend_count > 0 
                ? Math.round((regionStats.healthy_backends / regionStats.backend_count) * 100) 
                : 0;
                
            let statusClass = 'success';
            if (healthPct < 50) statusClass = 'danger';
            else if (healthPct < 80) statusClass = 'warning';
            
            healthCell.innerHTML = `
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar bg-${statusClass}" role="progressbar" style="width: ${healthPct}%" 
                    aria-valuenow="${healthPct}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
                <div class="small text-muted mt-1">${healthPct}% healthy</div>
            `;
            row.appendChild(healthCell);
            
            // Add row to table
            tableBody.appendChild(row);
        }
    } catch (error) {
        console.error('Error updating region stats:', error);
    }
}

/**
 * Update backend details table
 * @param {Array} backends - Array of backend objects
 */
function updateBackendDetailsTable(backends) {
    // Get table body
    const tableBody = document.getElementById('backend-details-table').querySelector('tbody');
    tableBody.innerHTML = '';
    
    // Add rows for each backend
    backends.forEach(backend => {
        const row = document.createElement('tr');
        
        // Backend ID
        const idCell = document.createElement('td');
        idCell.textContent = backend.id;
        row.appendChild(idCell);
        
        // Chip type
        const chipCell = document.createElement('td');
        chipCell.textContent = backend.chip_type;
        row.appendChild(chipCell);
        
        // Region
        const regionCell = document.createElement('td');
        regionCell.textContent = backend.region;
        row.appendChild(regionCell);
        
        // Models
        const modelsCell = document.createElement('td');
        modelsCell.className = 'backend-models';
        modelsCell.setAttribute('title', backend.supported_models.join(', '));
        modelsCell.textContent = backend.supported_models.join(', ');
        row.appendChild(modelsCell);
        
        // Status
        const statusCell = document.createElement('td');
        statusCell.innerHTML = formatStatus(backend.status);
        row.appendChild(statusCell);
        
        // Load
        const loadCell = document.createElement('td');
        const loadClass = backend.current_load > 80 ? 'danger' : (backend.current_load > 60 ? 'warning' : '');
        loadCell.innerHTML = `
            <div class="backend-load-bar">
                <div class="backend-load-fill ${loadClass}" style="width: ${backend.current_load}%"></div>
            </div>
            <div class="small text-muted mt-1">${backend.current_load.toFixed(1)}%</div>
        `;
        row.appendChild(loadCell);
        
        // Actions
        const actionsCell = document.createElement('td');
        actionsCell.innerHTML = `
            <button class="btn btn-sm btn-outline-primary select-backend-btn" data-backend-id="${backend.id}">
                <i class="fas fa-crosshairs"></i>
            </button>
        `;
        row.appendChild(actionsCell);
        
        // Add to table
        tableBody.appendChild(row);
    });
    
    // Add event listeners for action buttons
    document.querySelectorAll('.select-backend-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const backendId = btn.getAttribute('data-backend-id');
            selectBackend(backendId);
        });
    });
}

/**
 * Select a backend and show details
 * @param {string} backendId - Backend ID to select
 */
function selectBackend(backendId) {
    const backend = globalBackends.find(b => b.id === backendId);
    if (!backend) return;
    
    // Find the marker for this backend's region
    const marker = backendMarkers.find(m => m.region === backend.region);
    if (!marker) return;
    
    // Center map on region
    const coords = getRegionCoordinates(backend.region);
    map.setView([coords.lat, coords.lng], 4);
    
    // Open popup
    marker.openPopup();
    
    // Highlight the row in the table
    document.querySelectorAll('#backend-details-table tbody tr').forEach(row => {
        row.classList.remove('backend-row', 'selected');
    });
    
    const row = Array.from(document.querySelectorAll('#backend-details-table tbody tr')).find(
        row => row.cells[0].textContent === backendId
    );
    
    if (row) {
        row.classList.add('backend-row', 'selected');
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Update user region
 */
function updateUserRegion() {
    // Get selected region
    selectedRegion = document.getElementById('user-region').value;
    
    // Update user marker position
    const coords = getRegionCoordinates(selectedRegion);
    userMarker.setLatLng([coords.lat, coords.lng]);
    userMarker.getTooltip().setContent(`User Region: ${selectedRegion}`);
    
    // Clear any existing paths
    pathLayer.clearLayers();
    
    // Hide routing simulation card
    document.getElementById('routing-simulation-card').style.display = 'none';
}

/**
 * Show optimal paths from user region to backends
 */
function showOptimalPaths() {
    // Clear existing paths
    pathLayer.clearLayers();
    
    // Show routing simulation card
    document.getElementById('routing-simulation-card').style.display = 'block';
    
    // Populate models dropdown
    const modelSelect = document.getElementById('sim-model');
    modelSelect.innerHTML = '';
    
    globalModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
    
    // Populate compliance dropdown
    const complianceSelect = document.getElementById('sim-compliance');
    complianceSelect.innerHTML = '';
    
    globalComplianceTags.forEach(tag => {
        const option = document.createElement('option');
        option.value = tag;
        option.textContent = tag;
        complianceSelect.appendChild(option);
    });
    
    // Center map based on user position
    const userCoords = getRegionCoordinates(selectedRegion);
    map.setView([userCoords.lat, userCoords.lng], 2);
}

/**
 * Initialize routing simulation form
 */
function initializeRoutingSimulation() {
    // Set up latency slider
    const latencySlider = document.getElementById('sim-latency');
    const latencyValue = document.getElementById('sim-latency-value');
    
    latencySlider.addEventListener('input', () => {
        latencyValue.textContent = `${latencySlider.value}ms`;
    });
    
    // Set up form submission
    document.getElementById('path-simulation-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        
        // Get form values
        const model = document.getElementById('sim-model').value;
        const latency = parseInt(document.getElementById('sim-latency').value);
        
        // Get selected compliance tags
        const complianceSelect = document.getElementById('sim-compliance');
        const selectedTags = Array.from(complianceSelect.selectedOptions).map(option => option.value);
        
        // Prepare request
        const requestData = {
            model: model,
            token_size: 1000, // Default token size
            required_latency: latency,
            user_region: selectedRegion,
            compliance_tags: selectedTags,
            priority: 1 // Default priority
        };
        
        try {
            // Send routing request
            const response = await fetch('/api/route-request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            // Visualize the routing path
            visualizeRoutingPath(result);
            
        } catch (error) {
            console.error('Error in routing simulation:', error);
        }
    });
}

/**
 * Visualize routing path on the map
 * @param {Object} result - Routing result
 */
function visualizeRoutingPath(result) {
    // Clear existing paths
    pathLayer.clearLayers();
    
    // Show routing path display
    document.getElementById('routing-path-display').style.display = 'block';
    
    // Get user coordinates
    const userCoords = getRegionCoordinates(selectedRegion);
    
    // Create SVG for path visualization
    const svg = d3.select('#routing-path-display')
        .append('svg')
        .attr('width', '100%')
        .attr('height', '100%');
    
    // Create container for path visualization
    const container = svg.append('g')
        .attr('transform', 'translate(10, 10)');
    
    // Hide routing results initially
    document.getElementById('routing-results').style.display = 'none';
    
    if (result.decision.error) {
        // Show error message
        container.append('text')
            .attr('x', '50%')
            .attr('y', '50%')
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', '#e74c3c')
            .style('font-weight', 'bold')
            .text('No compatible backend found');
        
        return;
    }
    
    // Show routing results
    document.getElementById('routing-results').style.display = 'block';
    
    // Get backend coordinates
    const backendCoords = getRegionCoordinates(result.decision.region);
    
    // Get network latency
    const networkLatency = getNetworkLatency(selectedRegion, result.decision.region);
    
    // Update routing results display
    document.getElementById('routing-backend').textContent = result.decision.chip_type;
    document.getElementById('routing-region').textContent = result.decision.region;
    document.getElementById('routing-network-latency').textContent = `${networkLatency} ms`;
    document.getElementById('routing-processing-latency').textContent = 
        `${result.decision.final_latency_ms - networkLatency - result.decision.estimated_queue_time_ms} ms`;
    document.getElementById('routing-total-latency').textContent = `${result.decision.final_latency_ms} ms`;
    document.getElementById('routing-cost').textContent = `$${result.decision.final_cost.toFixed(6)}`;
    
    // Draw routing path on actual map
    const routingPath = L.polyline(
        [[userCoords.lat, userCoords.lng], [backendCoords.lat, backendCoords.lng]],
        {
            color: result.is_fallback ? '#f39c12' : '#3498db',
            weight: 3,
            opacity: 0.8,
            dashArray: '10, 10',
            lineCap: 'round'
        }
    ).addTo(pathLayer);
    
    // Add arrow in the middle of the path
    const midPoint = L.latLng(
        (userCoords.lat + backendCoords.lat) / 2,
        (userCoords.lng + backendCoords.lng) / 2
    );
    
    // Calculate angle for arrow
    const angle = Math.atan2(
        backendCoords.lat - userCoords.lat,
        backendCoords.lng - userCoords.lng
    ) * 180 / Math.PI;
    
    const arrowMarker = L.marker(midPoint, {
        icon: L.divIcon({
            className: 'path-arrow',
            html: `<div style="transform:rotate(${angle}deg); font-size:24px; color:${result.is_fallback ? '#f39c12' : '#3498db'}">➔</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        })
    }).addTo(pathLayer);
    
    // Draw nodes and connections in the visualization
    
    // Position for user node
    const userX = 20;
    const userY = 110;
    
    // Position for router node
    const routerX = 150;
    const routerY = 110;
    
    // Position for backend node
    const backendX = 280;
    const backendY = 110;
    
    // Draw user node
    container.append('circle')
        .attr('cx', userX)
        .attr('cy', userY)
        .attr('r', 10)
        .attr('fill', '#3498db')
        .attr('stroke', 'white')
        .attr('stroke-width', 2);
    
    container.append('text')
        .attr('x', userX)
        .attr('y', userY - 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text('User');
    
    container.append('text')
        .attr('x', userX)
        .attr('y', userY - 5)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .text(selectedRegion);
    
    // Draw router node
    container.append('rect')
        .attr('x', routerX - 15)
        .attr('y', routerY - 15)
        .attr('width', 30)
        .attr('height', 30)
        .attr('rx', 5)
        .attr('ry', 5)
        .attr('fill', '#9b59b6')
        .attr('stroke', 'white')
        .attr('stroke-width', 2);
    
    container.append('text')
        .attr('x', routerX)
        .attr('y', routerY - 25)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text('Tesseract Router');
    
    // Draw backend node
    const backendColor = result.is_fallback ? '#f39c12' : '#2ecc71';
    const backendLabel = result.is_fallback ? 'Fallback Backend' : 'Selected Backend';
    
    container.append('circle')
        .attr('cx', backendX)
        .attr('cy', backendY)
        .attr('r', 10)
        .attr('fill', backendColor)
        .attr('stroke', 'white')
        .attr('stroke-width', 2);
    
    container.append('text')
        .attr('x', backendX)
        .attr('y', backendY - 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text(backendLabel);
    
    container.append('text')
        .attr('x', backendX)
        .attr('y', backendY - 5)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .text(`${result.decision.chip_type}`);
    
    // Draw paths between nodes
    // User -> Router
    container.append('line')
        .attr('x1', userX + 15)
        .attr('y1', userY)
        .attr('x2', routerX - 20)
        .attr('y2', routerY)
        .attr('stroke', '#3498db')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5');
    
    // Router -> Backend
    container.append('line')
        .attr('x1', routerX + 20)
        .attr('y1', routerY)
        .attr('x2', backendX - 15)
        .attr('y2', backendY)
        .attr('stroke', backendColor)
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '5,5');
    
    // Add latency labels
    container.append('text')
        .attr('x', (userX + routerX) / 2)
        .attr('y', userY - 10)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#555')
        .text(`${networkLatency}ms`);
        
    const processingLatency = result.decision.final_latency_ms - networkLatency - result.decision.estimated_queue_time_ms;
    container.append('text')
        .attr('x', (routerX + backendX) / 2)
        .attr('y', userY - 10)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#555')
        .text(`${processingLatency}ms`);
    
    // Add region info
    container.append('text')
        .attr('x', backendX)
        .attr('y', backendY + 25)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#555')
        .text(result.decision.region);
}

/**
 * Show a toast notification
 * @param {string} title - Toast title
 * @param {string} message - Toast message
 */
function showToast(title, message) {
    // Check if Bootstrap is available
    if (typeof bootstrap === 'undefined') {
        alert(`${title}: ${message}`);
        return;
    }
    
    // Create toast element
    const toastEl = document.createElement('div');
    toastEl.className = 'toast';
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    
    toastEl.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto">${title}</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    // Add to document
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = 1070;
    
    toastContainer.appendChild(toastEl);
    document.body.appendChild(toastContainer);
    
    // Show toast
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    
    // Remove container after toast is hidden
    toastEl.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toastContainer);
    });
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', initMap);