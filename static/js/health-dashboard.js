/**
 * Health Dashboard JavaScript
 */

// Global variables
let hardwareDistributionChart = null;
let modelCoverageChart = null;
let loadDistributionChart = null;
let queueTimeChart = null;

/**
 * Initialize the health dashboard
 */
function initHealthDashboard() {
    // Load dashboard data
    loadDashboardData();
    
    // Set up event listeners
    document.getElementById('refresh-dashboard-btn').addEventListener('click', loadDashboardData);
    document.getElementById('simulate-fluctuation-dashboard-btn').addEventListener('click', simulateFluctuation);
    
    // Set up filter event listeners
    document.getElementById('show-healthy').addEventListener('change', filterBackendsTable);
    document.getElementById('show-degraded').addEventListener('change', filterBackendsTable);
    document.getElementById('show-down').addEventListener('change', filterBackendsTable);
    
    // Set up interval refresh (every 30 seconds)
    setInterval(loadDashboardData, 30000);
}

/**
 * Load dashboard data
 */
async function loadDashboardData() {
    try {
        // Fetch backends data
        const backends = await fetchBackends();
        
        // Fetch dashboard data
        const response = await fetch('/api/dashboard-data');
        const dashboardData = await response.json();
        
        // Update dashboard components
        updateMetricsCards(dashboardData.router_stats);
        createHealthHeatmap(dashboardData.region_chip_distribution);
        updateHardwareDistributionChart(dashboardData.chip_distribution);
        updateModelCoverageChart(backends);
        updateLoadDistributionChart(backends);
        updateQueueTimeChart(backends);
        updateBackendsTable(backends);
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

/**
 * Update the metrics cards
 * @param {Object} stats - Router statistics
 */
function updateMetricsCards(stats) {
    document.getElementById('healthy-count').textContent = stats.healthy_backends;
    document.getElementById('degraded-count').textContent = stats.degraded_backends;
    document.getElementById('down-count').textContent = stats.down_backends;
    document.getElementById('avg-load').textContent = `${stats.avg_system_load.toFixed(1)}%`;
}

/**
 * Create the health heatmap
 * @param {Object} regionChipDistribution - Distribution of chips by region
 */
function createHealthHeatmap(regionChipDistribution) {
    const container = document.getElementById('health-heatmap');
    container.innerHTML = '';
    
    // Get all unique regions and chip types
    const regions = Object.keys(regionChipDistribution);
    
    const allChipTypes = new Set();
    regions.forEach(region => {
        Object.keys(regionChipDistribution[region]).forEach(chipType => {
            allChipTypes.add(chipType);
        });
    });
    
    const chipTypes = Array.from(allChipTypes).sort();
    
    // Create table for heatmap
    const table = document.createElement('table');
    table.className = 'heatmap-table';
    
    // Create header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    // Empty cell for top-left corner
    headerRow.appendChild(document.createElement('th'));
    
    // Chip type headers
    chipTypes.forEach(chipType => {
        const th = document.createElement('th');
        th.textContent = chipType;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    
    // Create row for each region
    regions.forEach(region => {
        const row = document.createElement('tr');
        
        // Region name
        const regionCell = document.createElement('th');
        regionCell.textContent = region;
        row.appendChild(regionCell);
        
        // Cells for each chip type
        chipTypes.forEach(chipType => {
            const td = document.createElement('td');
            
            // Check if this region has this chip type
            if (regionChipDistribution[region][chipType]) {
                // Get backends of this chip type in this region
                const count = regionChipDistribution[region][chipType];
                
                // Get status from global backends data
                let healthyCount = 0;
                let degradedCount = 0;
                let downCount = 0;
                
                globalBackends
                    .filter(b => b.region === region && b.chip_type === chipType)
                    .forEach(backend => {
                        if (backend.status === 'healthy') healthyCount++;
                        else if (backend.status === 'degraded') degradedCount++;
                        else if (backend.status === 'down') downCount++;
                    });
                
                // Determine cell status class
                let statusClass = 'healthy';
                if (healthyCount === 0) {
                    statusClass = downCount > 0 ? 'down' : 'degraded';
                } else if (healthyCount < count / 2) {
                    statusClass = 'degraded';
                }
                
                // Create cell content
                td.className = `heatmap-cell heatmap-cell-${statusClass}`;
                td.innerHTML = `
                    <div class="heatmap-status">${count}</div>
                    <div class="heatmap-label">${chipType}</div>
                    <div class="heatmap-count">
                        <span style="color: rgba(255,255,255,0.9)">H: ${healthyCount}</span> | 
                        <span style="color: rgba(255,255,255,0.9)">D: ${degradedCount}</span> | 
                        <span style="color: rgba(255,255,255,0.9)">X: ${downCount}</span>
                    </div>
                `;
                
                // Add tooltip
                td.setAttribute('data-bs-toggle', 'tooltip');
                td.setAttribute('data-bs-placement', 'top');
                td.setAttribute('title', `${chipType} in ${region}\nHealthy: ${healthyCount}, Degraded: ${degradedCount}, Down: ${downCount}`);
            } else {
                // Empty cell
                td.className = 'heatmap-cell heatmap-cell-empty';
                td.innerHTML = `<div class="heatmap-status">-</div>`;
            }
            
            row.appendChild(td);
        });
        
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    container.appendChild(table);
    
    // Initialize tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

/**
 * Update the hardware distribution chart
 * @param {Object} distribution - Chip distribution data
 */
function updateHardwareDistributionChart(distribution) {
    const ctx = document.getElementById('hardware-distribution-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (hardwareDistributionChart) {
        hardwareDistributionChart.destroy();
    }
    
    // Prepare data
    const labels = Object.keys(distribution);
    const data = Object.values(distribution);
    const backgroundColors = labels.map(label => getChipColor(label));
    
    // Create chart
    hardwareDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderColor: '#fff',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        padding: 10,
                        font: {
                            size: 10
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            cutout: '70%',
            animation: {
                animateScale: true
            }
        }
    });
}

/**
 * Update the model coverage chart
 * @param {Array} backends - Backends data
 */
function updateModelCoverageChart(backends) {
    const ctx = document.getElementById('model-coverage-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (modelCoverageChart) {
        modelCoverageChart.destroy();
    }
    
    // Count model occurrences
    const modelCounts = {};
    backends.forEach(backend => {
        backend.supported_models.forEach(model => {
            if (!modelCounts[model]) {
                modelCounts[model] = 0;
            }
            modelCounts[model]++;
        });
    });
    
    // Sort models by count (descending)
    const sortedModels = Object.entries(modelCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10); // Top 10 models
    
    const labels = sortedModels.map(entry => entry[0]);
    const data = sortedModels.map(entry => entry[1]);
    
    // Create chart
    modelCoverageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Backends Supporting',
                data: data,
                backgroundColor: 'rgba(52, 152, 219, 0.7)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Model Support (Top 10)',
                    font: {
                        size: 14
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Backends'
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

/**
 * Update the load distribution chart
 * @param {Array} backends - Backends data
 */
function updateLoadDistributionChart(backends) {
    const ctx = document.getElementById('load-distribution-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (loadDistributionChart) {
        loadDistributionChart.destroy();
    }
    
    // Create load distribution buckets
    const loadBuckets = {
        '0-20%': 0,
        '20-40%': 0,
        '40-60%': 0,
        '60-80%': 0,
        '80-100%': 0
    };
    
    backends.forEach(backend => {
        const load = backend.current_load;
        if (load < 20) loadBuckets['0-20%']++;
        else if (load < 40) loadBuckets['20-40%']++;
        else if (load < 60) loadBuckets['40-60%']++;
        else if (load < 80) loadBuckets['60-80%']++;
        else loadBuckets['80-100%']++;
    });
    
    const labels = Object.keys(loadBuckets);
    const data = Object.values(loadBuckets);
    
    // Create colors based on load level
    const colors = [
        'rgba(46, 204, 113, 0.7)',   // 0-20% (green)
        'rgba(46, 204, 113, 0.5)',   // 20-40% (light green)
        'rgba(241, 196, 15, 0.7)',   // 40-60% (yellow)
        'rgba(230, 126, 34, 0.7)',   // 60-80% (orange)
        'rgba(231, 76, 60, 0.7)'     // 80-100% (red)
    ];
    
    // Create chart
    loadDistributionChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Backends',
                data: data,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace('0.7', '1')),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Backend Load Distribution',
                    font: {
                        size: 14
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Backends'
                    }
                }
            }
        }
    });
}

/**
 * Update the queue time chart
 * @param {Array} backends - Backends data
 */
function updateQueueTimeChart(backends) {
    const ctx = document.getElementById('queue-time-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (queueTimeChart) {
        queueTimeChart.destroy();
    }
    
    // Group queue times by chip type
    const chipQueueTimes = {};
    
    backends.forEach(backend => {
        if (!chipQueueTimes[backend.chip_type]) {
            chipQueueTimes[backend.chip_type] = [];
        }
        chipQueueTimes[backend.chip_type].push(backend.estimated_queue_time_ms);
    });
    
    // Calculate average queue time for each chip type
    const averageQueueTimes = {};
    for (const [chipType, times] of Object.entries(chipQueueTimes)) {
        const sum = times.reduce((a, b) => a + b, 0);
        averageQueueTimes[chipType] = sum / times.length;
    }
    
    // Sort by average queue time (descending)
    const sortedEntries = Object.entries(averageQueueTimes)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8); // Top 8 chip types
    
    const labels = sortedEntries.map(entry => entry[0]);
    const data = sortedEntries.map(entry => entry[1]);
    const colors = labels.map(label => getChipColor(label));
    
    // Create chart
    queueTimeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Average Queue Time (ms)',
                data: data,
                backgroundColor: colors.map(c => `${c}77`), // Add transparency
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Average Queue Time by Chip Type',
                    font: {
                        size: 14
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Queue Time (ms)'
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

/**
 * Update the backends table
 * @param {Array} backends - Backends data
 */
function updateBackendsTable(backends) {
    const tableBody = document.getElementById('backends-table').querySelector('tbody');
    tableBody.innerHTML = '';
    
    // Sort backends by status (healthy first, then degraded, then down)
    const sortedBackends = [...backends].sort((a, b) => {
        const statusOrder = { 'healthy': 0, 'degraded': 1, 'down': 2 };
        return statusOrder[a.status] - statusOrder[b.status];
    });
    
    // Add rows for each backend
    sortedBackends.forEach(backend => {
        const row = document.createElement('tr');
        row.setAttribute('data-status', backend.status);
        
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
        
        // Status
        const statusCell = document.createElement('td');
        statusCell.innerHTML = `<span class="backend-status backend-status-${backend.status}"></span> ${backend.status.charAt(0).toUpperCase() + backend.status.slice(1)}`;
        row.appendChild(statusCell);
        
        // Load
        const loadCell = document.createElement('td');
        const loadClass = backend.current_load > 80 ? 'danger' : (backend.current_load > 60 ? 'warning' : '');
        loadCell.innerHTML = `
            <div class="load-bar">
                <div class="load-bar-fill ${loadClass}" style="width: ${backend.current_load}%"></div>
            </div>
            <div class="small text-muted mt-1">${backend.current_load.toFixed(1)}%</div>
        `;
        row.appendChild(loadCell);
        
        // Queue time
        const queueCell = document.createElement('td');
        queueCell.textContent = `${backend.estimated_queue_time_ms} ms`;
        row.appendChild(queueCell);
        
        // Actions
        const actionsCell = document.createElement('td');
        actionsCell.innerHTML = `
            <button class="btn btn-sm btn-outline-primary edit-backend-btn" data-backend-id="${backend.id}">
                <i class="fas fa-edit"></i>
            </button>
        `;
        row.appendChild(actionsCell);
        
        // Add to table
        tableBody.appendChild(row);
    });
    
    // Add event listeners for edit buttons
    document.querySelectorAll('.edit-backend-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const backendId = btn.getAttribute('data-backend-id');
            openEditBackendModal(backendId);
        });
    });
    
    // Apply filters
    filterBackendsTable();
}

/**
 * Filter the backends table based on status checkboxes
 */
function filterBackendsTable() {
    const showHealthy = document.getElementById('show-healthy').checked;
    const showDegraded = document.getElementById('show-degraded').checked;
    const showDown = document.getElementById('show-down').checked;
    
    document.querySelectorAll('#backends-table tbody tr').forEach(row => {
        const status = row.getAttribute('data-status');
        
        if (status === 'healthy' && !showHealthy) {
            row.style.display = 'none';
        } else if (status === 'degraded' && !showDegraded) {
            row.style.display = 'none';
        } else if (status === 'down' && !showDown) {
            row.style.display = 'none';
        } else {
            row.style.display = '';
        }
    });
}

/**
 * Open the edit backend modal for a specific backend
 * @param {string} backendId - ID of the backend to edit
 */
function openEditBackendModal(backendId) {
    const backend = globalBackends.find(b => b.id === backendId);
    if (!backend) return;
    
    // Set modal values
    document.getElementById('edit-backend-id').value = backendId;
    document.getElementById('edit-backend-status').value = backend.status;
    
    const loadSlider = document.getElementById('edit-backend-load');
    loadSlider.value = backend.current_load;
    document.getElementById('load-value').textContent = `${backend.current_load.toFixed(1)}%`;
    
    // Set up load slider event listener
    loadSlider.addEventListener('input', () => {
        document.getElementById('load-value').textContent = `${loadSlider.value}%`;
    });
    
    // Set up save button event listener
    document.getElementById('save-backend-changes').onclick = saveBackendChanges;
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('edit-backend-modal'));
    modal.show();
}

/**
 * Save backend changes
 */
async function saveBackendChanges() {
    const backendId = document.getElementById('edit-backend-id').value;
    const status = document.getElementById('edit-backend-status').value;
    const load = parseFloat(document.getElementById('edit-backend-load').value);
    
    try {
        const response = await fetch('/api/update-backend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                backend_id: backendId,
                status: status,
                load: load
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Reload dashboard data
            loadDashboardData();
            
            // Hide the modal
            const modalEl = document.getElementById('edit-backend-modal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
            
            // Show success toast
            showToast('Backend Updated', `Backend ${backendId} has been updated successfully.`);
        } else {
            console.error('Failed to update backend:', result.error);
        }
    } catch (error) {
        console.error('Error updating backend:', error);
    }
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
            // Reload dashboard data
            loadDashboardData();
            
            // Show toast notification
            showToast('Backend Fluctuation Simulated', 'Random backend status changes have been applied.');
        }
    } catch (error) {
        console.error('Error simulating fluctuation:', error);
    }
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

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', initHealthDashboard);