/**
 * Latency Visualization JavaScript
 */

// Global variables
let costLatencyChart = null;
let chipComparisonChart = null;

/**
 * Initialize the latency visualization page
 */
function initLatencyViz() {
    // Load data
    loadLatencyData();
    
    // Set up event listeners
    document.getElementById('highlight-user-region').addEventListener('change', updateLatencyHeatmap);
    document.getElementById('user-region-select').addEventListener('change', updateLatencyHeatmap);
    
    // Set up cost vs latency controls
    document.getElementById('cost-latency-model').addEventListener('change', updateCostLatencyChart);
    document.getElementById('cost-latency-tokens').addEventListener('change', updateCostLatencyChart);
    
    // Set up chip comparison controls
    document.getElementById('chip-compare-model').addEventListener('change', updateChipComparisonChart);
    document.getElementById('performance-metric').addEventListener('change', updateChipComparisonChart);
    
    // Set up latency simulation form
    document.getElementById('latency-simulation-form').addEventListener('submit', handleLatencySimulation);
    
    // Set up token size slider
    const tokenSizeSlider = document.getElementById('sim-token-size');
    const tokenSizeValue = document.getElementById('sim-token-size-value');
    
    tokenSizeSlider.addEventListener('input', () => {
        const value = parseInt(tokenSizeSlider.value).toLocaleString();
        tokenSizeValue.textContent = `${value} tokens`;
    });
    
    // Set up latency slider
    const latencySlider = document.getElementById('sim-latency-req');
    const latencyValue = document.getElementById('sim-latency-req-value');
    
    latencySlider.addEventListener('input', () => {
        latencyValue.textContent = `${latencySlider.value}ms`;
    });
}

/**
 * Load latency visualization data
 */
async function loadLatencyData() {
    try {
        // Fetch backends
        const backends = await fetchBackends();
        
        // Fetch latency map
        const latencyMap = await fetchLatencyMap();
        
        // Create latency heatmap
        createLatencyHeatmap(latencyMap);
        
        // Initialize cost vs latency chart
        initCostLatencyChart(backends);
        
        // Initialize chip comparison chart
        initChipComparisonChart(backends);
        
        // Populate models dropdowns
        populateModelsDropdowns(backends);
        
    } catch (error) {
        console.error('Error loading latency data:', error);
    }
}

/**
 * Create the latency heatmap
 * @param {Object} latencyMap - Network latency map
 */
function createLatencyHeatmap(latencyMap) {
    const container = document.getElementById('latency-heatmap');
    container.innerHTML = '';
    
    // Get all regions
    const regions = Object.keys(latencyMap).sort();
    
    // Get the current user region
    const userRegion = document.getElementById('user-region-select').value;
    const highlightUserRegion = document.getElementById('highlight-user-region').checked;
    
    // Create table for heatmap
    const table = document.createElement('table');
    table.className = 'latency-table';
    
    // Create header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    // Empty cell for top-left corner
    const cornerCell = document.createElement('th');
    cornerCell.textContent = 'From / To';
    headerRow.appendChild(cornerCell);
    
    // Region column headers
    regions.forEach(region => {
        const th = document.createElement('th');
        th.textContent = region;
        
        // Highlight user region if specified
        if (highlightUserRegion && region === userRegion) {
            th.className = 'highlighted';
        }
        
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    
    // Create row for each source region
    regions.forEach(fromRegion => {
        const row = document.createElement('tr');
        
        // Region name
        const regionCell = document.createElement('th');
        regionCell.textContent = fromRegion;
        
        // Highlight user region if specified
        if (highlightUserRegion && fromRegion === userRegion) {
            regionCell.className = 'highlighted';
        }
        
        row.appendChild(regionCell);
        
        // Cells for each destination region
        regions.forEach(toRegion => {
            const td = document.createElement('td');
            
            // Get latency
            const latency = latencyMap[fromRegion][toRegion] || 0;
            
            // Skip same region (diagonal)
            if (fromRegion === toRegion) {
                td.textContent = '-';
                td.className = 'latency-na';
            } else {
                // Determine latency class
                let latencyClass = 'low';
                if (latency > 150) {
                    latencyClass = 'high';
                } else if (latency > 50) {
                    latencyClass = 'medium';
                }
                
                td.textContent = latency;
                td.className = `latency-cell latency-${latencyClass}`;
                
                // Highlight cells related to user region if specified
                if (highlightUserRegion && (fromRegion === userRegion || toRegion === userRegion)) {
                    td.className += ' highlighted';
                }
            }
            
            row.appendChild(td);
        });
        
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    container.appendChild(table);
}

/**
 * Update the latency heatmap based on user region
 */
function updateLatencyHeatmap() {
    // Re-create the heatmap with the updated user region
    createLatencyHeatmap(globalLatencyMap);
}

/**
 * Initialize the cost vs latency chart
 * @param {Array} backends - Array of backend objects
 */
function initCostLatencyChart(backends) {
    // Populate models dropdown
    const modelSelect = document.getElementById('cost-latency-model');
    modelSelect.innerHTML = '';
    
    globalModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
    
    // Update chart with initial values
    updateCostLatencyChart();
}

/**
 * Update the cost vs latency chart
 */
function updateCostLatencyChart() {
    const model = document.getElementById('cost-latency-model').value;
    const tokenSize = parseInt(document.getElementById('cost-latency-tokens').value);
    
    // Get backends that support this model
    const supportingBackends = globalBackends.filter(backend => 
        backend.supported_models.includes(model) && backend.status !== 'down'
    );
    
    // Prepare data
    const data = supportingBackends.map(backend => ({
        x: backend.latency_ms,
        y: backend.cost_per_token * tokenSize,
        chip: backend.chip_type,
        region: backend.region,
        load: backend.current_load,
        queue: backend.estimated_queue_time_ms
    }));
    
    // Create or update chart
    const ctx = document.getElementById('cost-latency-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (costLatencyChart) {
        costLatencyChart.destroy();
    }
    
    // Create chart
    costLatencyChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Backends',
                data: data,
                backgroundColor: data.map(item => `${getChipColor(item.chip)}aa`),
                borderColor: data.map(item => getChipColor(item.chip)),
                borderWidth: 1,
                pointRadius: 8,
                pointHoverRadius: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Latency (ms)'
                    },
                    beginAtZero: true
                },
                y: {
                    title: {
                        display: true,
                        text: 'Cost (USD)'
                    },
                    beginAtZero: true,
                    ticks: {
                        callback: value => `$${value.toFixed(6)}`
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const point = context.raw;
                            return [
                                `${point.chip} in ${point.region}`,
                                `Latency: ${point.x} ms`,
                                `Cost: $${point.y.toFixed(6)}`,
                                `Load: ${point.load.toFixed(1)}%`,
                                `Queue Time: ${point.queue} ms`
                            ];
                        }
                    }
                },
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: `Cost vs. Latency for ${model} (${tokenSize.toLocaleString()} tokens)`,
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
}

/**
 * Initialize the chip comparison chart
 * @param {Array} backends - Array of backend objects
 */
function initChipComparisonChart(backends) {
    // Populate models dropdown
    const modelSelect = document.getElementById('chip-compare-model');
    modelSelect.innerHTML = '';
    
    globalModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        modelSelect.appendChild(option);
    });
    
    // Update chart with initial values
    updateChipComparisonChart();
}

/**
 * Update the chip comparison chart
 */
function updateChipComparisonChart() {
    const model = document.getElementById('chip-compare-model').value;
    const metric = document.getElementById('performance-metric').value;
    
    // Get backends that support this model
    const supportingBackends = globalBackends.filter(backend => 
        backend.supported_models.includes(model) && backend.status !== 'down'
    );
    
    // Group by chip type
    const chipData = {};
    supportingBackends.forEach(backend => {
        if (!chipData[backend.chip_type]) {
            chipData[backend.chip_type] = [];
        }
        
        let value;
        if (metric === 'latency') {
            value = backend.latency_ms;
        } else if (metric === 'cost') {
            value = backend.cost_per_token * 1000; // Cost per 1K tokens
        } else if (metric === 'performance') {
            // Performance is defined as 1 / (latency * cost_per_token)
            // Higher is better
            value = 1 / (backend.latency_ms * backend.cost_per_token);
        }
        
        chipData[backend.chip_type].push(value);
    });
    
    // Calculate average for each chip type
    const averageData = {};
    for (const [chip, values] of Object.entries(chipData)) {
        const sum = values.reduce((a, b) => a + b, 0);
        averageData[chip] = sum / values.length;
    }
    
    // Sort by the metric (ascending for latency and cost, descending for performance)
    const sortedEntries = Object.entries(averageData).sort((a, b) => {
        if (metric === 'performance') {
            return b[1] - a[1]; // Higher is better for performance
        } else {
            return a[1] - b[1]; // Lower is better for latency and cost
        }
    });
    
    const labels = sortedEntries.map(entry => entry[0]);
    const data = sortedEntries.map(entry => entry[1]);
    const colors = labels.map(label => getChipColor(label));
    
    // Create or update chart
    const ctx = document.getElementById('chip-comparison-chart').getContext('2d');
    
    // Clean up previous chart if it exists
    if (chipComparisonChart) {
        chipComparisonChart.destroy();
    }
    
    // Determine y-axis label based on metric
    let yAxisLabel = 'Latency (ms)';
    let tooltipFormat = value => `${value.toFixed(2)} ms`;
    
    if (metric === 'cost') {
        yAxisLabel = 'Cost per 1K tokens (USD)';
        tooltipFormat = value => `$${value.toFixed(6)}`;
    } else if (metric === 'performance') {
        yAxisLabel = 'Performance Score';
        tooltipFormat = value => `${value.toFixed(2)}`;
    }
    
    // Determine title based on metric
    let chartTitle = 'Chip Latency Comparison';
    
    if (metric === 'cost') {
        chartTitle = 'Chip Cost Comparison';
    } else if (metric === 'performance') {
        chartTitle = 'Chip Performance Comparison';
    }
    
    // Create chart
    chipComparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: metric === 'performance' ? 'Higher is better' : 'Lower is better',
                data: data,
                backgroundColor: colors.map(c => `${c}77`), // Add transparency
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    title: {
                        display: true,
                        text: yAxisLabel
                    },
                    beginAtZero: true
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${tooltipFormat(context.raw)}`;
                        }
                    }
                },
                title: {
                    display: true,
                    text: `${chartTitle} for ${model}`,
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
}

/**
 * Populate models dropdowns
 * @param {Array} backends - Array of backend objects
 */
function populateModelsDropdowns(backends) {
    // Extract all models
    const models = globalModels;
    
    // Populate sim-model-select dropdown
    const simModelSelect = document.getElementById('sim-model-select');
    simModelSelect.innerHTML = '';
    
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        simModelSelect.appendChild(option);
    });
}

/**
 * Handle latency simulation form submission
 * @param {Event} event - Form submission event
 */
async function handleLatencySimulation(event) {
    event.preventDefault();
    
    // Get form values
    const fromRegion = document.getElementById('sim-from-region').value;
    const model = document.getElementById('sim-model-select').value;
    const tokenSize = parseInt(document.getElementById('sim-token-size').value);
    const requiredLatency = parseInt(document.getElementById('sim-latency-req').value);
    const preferCost = document.getElementById('sim-prefer-cost').checked;
    
    // Prepare request data
    const requestData = {
        model: model,
        token_size: tokenSize,
        required_latency: requiredLatency,
        user_region: fromRegion,
        compliance_tags: [], // No compliance constraints for this simulation
        priority: 1, // Default priority
        prefer_cost: preferCost
    };
    
    try {
        // Show loading state
        const submitButton = document.querySelector('#latency-simulation-form button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Simulating...';
        
        // Send routing request
        const response = await fetch('/api/route-request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        // Visualize the latency breakdown
        visualizeLatencyBreakdown(result, requiredLatency);
        
    } catch (error) {
        console.error('Error in latency simulation:', error);
    } finally {
        // Reset button
        const submitButton = document.querySelector('#latency-simulation-form button[type="submit"]');
        submitButton.disabled = false;
        submitButton.innerHTML = 'Simulate';
    }
}

/**
 * Visualize the latency breakdown
 * @param {Object} result - Routing result
 * @param {number} requiredLatency - Required latency SLA
 */
function visualizeLatencyBreakdown(result) {
    // Show the breakdown container
    document.getElementById('latency-breakdown-container').style.display = 'block';
    document.getElementById('no-results-message').style.display = 'none';
    
    // Get the breakdown visualization container
    const container = document.getElementById('latency-breakdown-viz');
    container.innerHTML = '';
    
    if (result.decision.error) {
        // Show error message
        container.innerHTML = `
            <div class="text-center py-4">
                <div class="text-danger mb-2"><i class="fas fa-exclamation-circle fa-3x"></i></div>
                <h5>No Compatible Backend Found</h5>
                <p class="text-muted">${result.decision.error}</p>
            </div>
        `;
        
        // Hide details
        document.getElementById('detail-network-latency').textContent = '-';
        document.getElementById('detail-queue-time').textContent = '-';
        document.getElementById('detail-processing-time').textContent = '-';
        document.getElementById('detail-total-latency').textContent = '-';
        document.getElementById('detail-sla-met').innerHTML = '<span class="badge bg-danger">No</span>';
        document.getElementById('detail-total-cost').textContent = '-';
        
        return;
    }
    
    // Get the user region
    const userRegion = document.getElementById('sim-from-region').value;
    
    // Get network latency from the global latency map
    const networkLatency = getNetworkLatency(userRegion, result.decision.region);
    
    // Get queue time
    const queueTime = result.decision.estimated_queue_time_ms || 0;
    
    // Get processing time (backend latency minus queue time)
    const processingLatency = result.decision.final_latency_ms - networkLatency - queueTime;
    
    // Get total latency
    const totalLatency = result.decision.final_latency_ms;
    
    // Get required latency
    const requiredLatency = parseInt(document.getElementById('sim-latency-req').value);
    
    // Create latency bar container
    const latencyBarContainer = document.createElement('div');
    latencyBarContainer.className = 'latency-bar-container';
    
    // Create latency bar
    const latencyBar = document.createElement('div');
    latencyBar.className = 'latency-bar';
    
    // Calculate percentages for each segment
    const networkPct = (networkLatency / totalLatency) * 100;
    const queuePct = (queueTime / totalLatency) * 100;
    const processingPct = (processingLatency / totalLatency) * 100;
    
    // Create network segment
    const networkSegment = document.createElement('div');
    networkSegment.className = 'latency-segment network-segment';
    networkSegment.style.width = `${networkPct}%`;
    networkSegment.setAttribute('title', `Network Latency: ${networkLatency} ms`);
    
    // Create queue segment
    const queueSegment = document.createElement('div');
    queueSegment.className = 'latency-segment queue-segment';
    queueSegment.style.width = `${queuePct}%`;
    queueSegment.style.left = `${networkPct}%`;
    queueSegment.setAttribute('title', `Queue Time: ${queueTime} ms`);
    
    // Create processing segment
    const processingSegment = document.createElement('div');
    processingSegment.className = 'latency-segment processing-segment';
    processingSegment.style.width = `${processingPct}%`;
    processingSegment.setAttribute('title', `Processing Time: ${processingLatency} ms`);
    
    // Add segments to bar
    latencyBar.appendChild(networkSegment);
    latencyBar.appendChild(queueSegment);
    latencyBar.appendChild(processingSegment);
    
    // Add SLA marker if it fits in the visualization
    if (requiredLatency <= totalLatency * 1.5) {
        const slaPct = (requiredLatency / totalLatency) * 100;
        
        const slaMarker = document.createElement('div');
        slaMarker.className = 'sla-marker';
        slaMarker.style.left = `${slaPct}%`;
        
        const slaLabel = document.createElement('div');
        slaLabel.className = 'sla-label';
        slaLabel.style.left = `${slaPct}%`;
        slaLabel.textContent = 'SLA';
        
        latencyBar.appendChild(slaMarker);
        latencyBar.appendChild(slaLabel);
    }
    
    // Add bar to container
    latencyBarContainer.appendChild(latencyBar);
    
    // Create labels
    const latencyLabels = document.createElement('div');
    latencyLabels.className = 'latency-labels';
    
    latencyLabels.innerHTML = `
        <div>0 ms</div>
        <div>${Math.round(totalLatency / 2)} ms</div>
        <div>${totalLatency} ms</div>
    `;
    
    latencyBarContainer.appendChild(latencyLabels);
    
    // Add container to visualization
    container.appendChild(latencyBarContainer);
    
    // Add legend
    const legend = document.createElement('div');
    legend.className = 'latency-legend';
    
    legend.innerHTML = `
        <div class="legend-item">
            <div class="legend-color legend-network"></div>
            <div class="legend-label">Network (${networkLatency} ms)</div>
        </div>
        <div class="legend-item">
            <div class="legend-color legend-queue"></div>
            <div class="legend-label">Queue (${queueTime} ms)</div>
        </div>
        <div class="legend-item">
            <div class="legend-color legend-processing"></div>
            <div class="legend-label">Processing (${processingLatency} ms)</div>
        </div>
        <div class="legend-item">
            <div class="legend-color legend-sla"></div>
            <div class="legend-label">SLA (${requiredLatency} ms)</div>
        </div>
    `;
    
    container.appendChild(legend);
    
    // Update details
    document.getElementById('detail-network-latency').textContent = `${networkLatency} ms`;
    document.getElementById('detail-queue-time').textContent = `${queueTime} ms`;
    document.getElementById('detail-processing-time').textContent = `${processingLatency} ms`;
    document.getElementById('detail-total-latency').textContent = `${totalLatency} ms`;
    
    const slaMet = result.sla_met 
        ? '<span class="badge bg-success">Yes</span>' 
        : '<span class="badge bg-danger">No</span>';
    document.getElementById('detail-sla-met').innerHTML = slaMet;
    
    document.getElementById('detail-total-cost').textContent = `${result.decision.final_cost.toFixed(6)}`;
}

// Initialize latency visualization when DOM is loaded
document.addEventListener('DOMContentLoaded', initLatencyViz);