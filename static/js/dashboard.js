/**
 * Main Dashboard JavaScript
 */

// Global variables
let chipDistributionChart = null;

/**
 * Initialize the dashboard
 */
function initDashboard() {
    // Fetch dashboard data
    fetchDashboardData();
    
    // Set up event listeners
    document.getElementById('quick-latency').addEventListener('input', updateLatencyLabel);
    document.getElementById('quick-route-form').addEventListener('submit', handleQuickRoute);
    document.getElementById('simulate-routes-btn').addEventListener('click', simulateRandomRoutes);
}

/**
 * Fetch dashboard data from API
 */
async function fetchDashboardData() {
    try {
        const response = await fetch('/api/dashboard-data');
        const data = await response.json();
        
        // Update dashboard stats
        updateSystemStats(data.router_stats);
        
        // Initialize charts
        initChipDistributionChart(data.chip_distribution);
        
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

/**
 * Update system statistics display
 * @param {Object} stats - System statistics
 */
function updateSystemStats(stats) {
    // Update counters
    document.getElementById('total-backends').textContent = stats.total_backends;
    document.getElementById('healthy-backends').textContent = stats.healthy_backends;
    document.getElementById('degraded-backends').textContent = stats.degraded_backends;
    document.getElementById('down-backends').textContent = stats.down_backends;
    
    // Update health bars
    const total = stats.total_backends;
    if (total > 0) {
        document.getElementById('health-bar-healthy').style.width = `${(stats.healthy_backends / total) * 100}%`;
        document.getElementById('health-bar-degraded').style.width = `${(stats.degraded_backends / total) * 100}%`;
        document.getElementById('health-bar-down').style.width = `${(stats.down_backends / total) * 100}%`;
    }
    
    // Update other stats
    document.getElementById('system-load').textContent = `${stats.avg_system_load.toFixed(1)}%`;
    document.getElementById('regions-count').textContent = stats.regions.length;
    document.getElementById('chip-types-count').textContent = stats.chip_types.length;
}

/**
 * Initialize the chip distribution chart
 * @param {Object} distribution - Chip distribution data
 */
function initChipDistributionChart(distribution) {
    const ctx = document.getElementById('chip-distribution-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (chipDistributionChart) {
        chipDistributionChart.destroy();
    }
    
    // Prepare data
    const labels = Object.keys(distribution);
    const data = Object.values(distribution);
    const backgroundColors = labels.map(label => getChipColor(label));
    
    // Create chart
    chipDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 15,
                        padding: 15,
                        font: {
                            size: 11
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
            cutout: '60%',
            animation: {
                animateScale: true
            }
        }
    });
}

/**
 * Update the latency label when slider changes
 */
function updateLatencyLabel() {
    const latencySlider = document.getElementById('quick-latency');
    const latencyValue = document.getElementById('quick-latency-value');
    latencyValue.textContent = `${latencySlider.value}ms`;
}

/**
 * Handle quick route form submission
 * @param {Event} event - Form submission event
 */
async function handleQuickRoute(event) {
    event.preventDefault();
    
    // Get form values
    const model = document.getElementById('quick-model').value;
    const region = document.getElementById('quick-region').value;
    const latency = document.getElementById('quick-latency').value;
    const simulateFailure = document.getElementById('quick-simulate-failure').checked;
    
    // Prepare request data
    const requestData = {
        model: model,
        token_size: 1000, // Default token size
        required_latency: parseInt(latency),
        user_region: region,
        compliance_tags: [], // No compliance constraints for quick route
        priority: 1, // Default to highest priority
        simulate_failure: simulateFailure
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
        
        // Display result
        displayQuickResult(result);
        
    } catch (error) {
        console.error('Error in quick route:', error);
    }
}

/**
 * Display quick route result
 * @param {Object} result - Routing result
 */
function displayQuickResult(result) {
    const resultCard = document.getElementById('quick-route-result');
    resultCard.style.display = 'block';
    
    // Get result elements
    const statusEl = document.getElementById('quick-result-status');
    const backendEl = document.getElementById('quick-result-backend');
    const regionEl = document.getElementById('quick-result-region');
    const latencyEl = document.getElementById('quick-result-latency');
    const costEl = document.getElementById('quick-result-cost');
    const slaEl = document.getElementById('quick-result-sla');
    
    // Display result information
    if (result.decision.error) {
        // No compatible backend found
        statusEl.innerHTML = '<span class="badge bg-danger">Failed</span>';
        backendEl.textContent = 'No compatible backend';
        regionEl.textContent = '-';
        latencyEl.textContent = '-';
        costEl.textContent = '-';
        slaEl.innerHTML = '<span class="badge bg-danger">No</span>';
    } else {
        // Backend found
        const status = result.is_fallback 
            ? '<span class="badge bg-warning">Fallback</span>' 
            : '<span class="badge bg-success">Routed</span>';
            
        statusEl.innerHTML = status;
        backendEl.textContent = result.decision.chip_type;
        regionEl.textContent = result.decision.region;
        latencyEl.textContent = `${result.decision.final_latency_ms} ms`;
        costEl.textContent = `$${result.decision.final_cost.toFixed(6)}`;
        
        const slaMet = result.sla_met 
            ? '<span class="badge bg-success">Yes</span>' 
            : '<span class="badge bg-danger">No</span>';
            
        slaEl.innerHTML = slaMet;
    }
}

/**
 * Simulate multiple random routes
 */
async function simulateRandomRoutes() {
    // Models to use for simulation
    const models = ['gpt-4', 'llama-3-70b', 'claude-3-opus', 'gemini-pro', 'mistral-large'];
    
    // Regions to use for simulation
    const regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-northeast-1'];
    
    // Latency requirements
    const latencies = [100, 200, 300, 500];
    
    // Number of routes to simulate
    const count = 5;
    
    // Get table body
    const tableBody = document.getElementById('recent-routes-table').querySelector('tbody');
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center">Simulating routes...</td></tr>';
    
    // Generate and process routes
    const routes = [];
    for (let i = 0; i < count; i++) {
        // Random model, region, and latency
        const model = models[Math.floor(Math.random() * models.length)];
        const region = regions[Math.floor(Math.random() * regions.length)];
        const latency = latencies[Math.floor(Math.random() * latencies.length)];
        
        // Prepare request data
        const requestData = {
            model: model,
            token_size: Math.floor(Math.random() * 8000) + 1000, // Random token size between 1000-9000
            required_latency: latency,
            user_region: region,
            compliance_tags: [], // No compliance constraints for simulation
            priority: Math.floor(Math.random() * 3) + 1, // Priority between 1-3
            simulate_failure: Math.random() < 0.2 // 20% chance of simulating failure
        };
        
        routes.push(requestData);
    }
    
    // Process routes sequentially
    tableBody.innerHTML = ''; // Clear table
    
    for (const route of routes) {
        try {
            // Send routing request
            const response = await fetch('/api/route-request', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(route)
            });
            
            const result = await response.json();
            
            // Add to table
            const row = document.createElement('tr');
            
            // Model
            const modelCell = document.createElement('td');
            modelCell.textContent = result.request_info.model;
            row.appendChild(modelCell);
            
            // Region
            const regionCell = document.createElement('td');
            if (result.decision.error) {
                regionCell.textContent = '-';
            } else {
                regionCell.textContent = result.decision.region;
            }
            row.appendChild(regionCell);
            
            // Backend
            const backendCell = document.createElement('td');
            if (result.decision.error) {
                backendCell.textContent = 'No compatible backend';
            } else {
                backendCell.textContent = result.decision.chip_type;
            }
            row.appendChild(backendCell);
            
            // Latency
            const latencyCell = document.createElement('td');
            if (result.decision.error) {
                latencyCell.textContent = '-';
            } else {
                latencyCell.textContent = `${result.decision.final_latency_ms}`;
            }
            row.appendChild(latencyCell);
            
            // SLA Met
            const slaCell = document.createElement('td');
            if (result.decision.error) {
                slaCell.innerHTML = '<span class="badge bg-danger">No</span>';
            } else {
                slaCell.innerHTML = result.sla_met 
                    ? '<span class="badge bg-success">Yes</span>' 
                    : '<span class="badge bg-danger">No</span>';
            }
            row.appendChild(slaCell);
            
            // Status
            const statusCell = document.createElement('td');
            if (result.decision.error) {
                statusCell.innerHTML = '<span class="badge bg-danger">Failed</span>';
            } else if (result.is_fallback) {
                statusCell.innerHTML = '<span class="badge bg-warning">Fallback</span>';
            } else {
                statusCell.innerHTML = '<span class="badge bg-success">Routed</span>';
            }
            row.appendChild(statusCell);
            
            // Add to table
            tableBody.appendChild(row);
            
            // Small delay to make it look like processing
            await new Promise(resolve => setTimeout(resolve, 300));
            
        } catch (error) {
            console.error('Error simulating route:', error);
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', initDashboard);