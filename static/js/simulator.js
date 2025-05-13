/**
 * Request Router Simulator JavaScript
 */

// Global variables
let batchResultsChart = null;
let batchResults = [];
let currentResult = null;

/**
 * Initialize the simulator page
 */
function initSimulator() {
    // Set up event listeners for form controls
    setupFormEventHandlers();
    
    // Initialize the form submission
    document.getElementById('routing-form').addEventListener('submit', handleRouteRequest);
    
    // Set up batch simulation buttons
    document.getElementById('simulate-5-btn').addEventListener('click', () => simulateBatch(5));
    document.getElementById('simulate-20-btn').addEventListener('click', () => simulateBatch(20));
    
    // Set up toggle filtered backends button
    document.getElementById('toggle-filtered-btn').addEventListener('click', toggleFilteredBackends);
}

/**
 * Set up event handlers for form controls
 */
function setupFormEventHandlers() {
    // Token size slider
    const tokenSizeSlider = document.getElementById('token-size');
    const tokenSizeValue = document.getElementById('token-size-value');
    
    tokenSizeSlider.addEventListener('input', () => {
        const value = parseInt(tokenSizeSlider.value);
        tokenSizeValue.textContent = value.toLocaleString() + ' tokens';
    });
    
    // Latency slider
    const latencySlider = document.getElementById('required-latency');
    const latencyValue = document.getElementById('latency-value');
    
    latencySlider.addEventListener('input', () => {
        latencyValue.textContent = latencySlider.value + 'ms';
    });
}

/**
 * Handle route request form submission
 * @param {Event} event - Form submission event
 */
async function handleRouteRequest(event) {
    event.preventDefault();
    
    // Get form values
    const model = document.getElementById('model-select').value;
    const tokenSize = parseInt(document.getElementById('token-size').value);
    const requiredLatency = parseInt(document.getElementById('required-latency').value);
    const userRegion = document.getElementById('user-region').value;
    const priority = parseInt(document.getElementById('priority').value);
    const maxCost = document.getElementById('max-cost').value ? parseFloat(document.getElementById('max-cost').value) : null;
    const preferCost = document.getElementById('prefer-cost').checked;
    const simulateFailure = document.getElementById('simulate-failure').checked;
    
    // Get selected compliance tags
    const complianceTags = [];
    document.querySelectorAll('.compliance-check:checked').forEach(checkbox => {
        complianceTags.push(checkbox.value);
    });
    
    // Prepare request data
    const requestData = {
        model: model,
        token_size: tokenSize,
        required_latency: requiredLatency,
        user_region: userRegion,
        compliance_tags: complianceTags,
        priority: priority,
        max_cost: maxCost,
        prefer_cost: preferCost,
        simulate_failure: simulateFailure
    };
    
    try {
        // Show loading state
        document.getElementById('routing-form').querySelector('button[type="submit"]').disabled = true;
        document.getElementById('routing-form').querySelector('button[type="submit"]').innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Routing...';
        
        // Send routing request
        const response = await fetch('/api/route-request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        currentResult = result;
        
        // Display result
        displayRoutingResult(result);
        
    } catch (error) {
        console.error('Error in route request:', error);
    } finally {
        // Reset form button
        document.getElementById('routing-form').querySelector('button[type="submit"]').disabled = false;
        document.getElementById('routing-form').querySelector('button[type="submit"]').innerHTML = 'Route Request';
    }
}

/**
 * Display routing result
 * @param {Object} result - Routing result from API
 */
function displayRoutingResult(result) {
    // Show the result card
    document.getElementById('routing-result-card').style.display = 'block';
    
    // Update request details
    document.getElementById('result-model').textContent = result.request_info.model;
    document.getElementById('result-tokens').textContent = result.request_info.input_tokens.toLocaleString() + ' tokens';
    document.getElementById('result-required-latency').textContent = result.request_info.required_latency_ms + ' ms';
    document.getElementById('result-compliance').textContent = result.request_info.compliance.length > 0 
        ? result.request_info.compliance.join(', ') 
        : 'None';
    document.getElementById('result-user-region').textContent = result.request_info.user_region || document.getElementById('user-region').value;
    
    // Visualize the routing path
    visualizeRoutingPath(result);
    
    // Update routing decision
    if (result.decision.error) {
        // No compatible backend
        document.getElementById('result-backend').textContent = 'No compatible backend';
        document.getElementById('result-backend-region').textContent = '-';
        document.getElementById('result-latency').textContent = '-';
        document.getElementById('result-sla').innerHTML = '<span class="badge bg-danger">No</span>';
        document.getElementById('result-cost').textContent = '-';
        document.getElementById('result-route-type').innerHTML = '<span class="badge bg-danger">Failed</span>';
    } else {
        // Backend found
        document.getElementById('result-backend').textContent = result.decision.chip_type;
        document.getElementById('result-backend-region').textContent = result.decision.region;
        document.getElementById('result-latency').textContent = result.decision.final_latency_ms + ' ms';
        
        const slaMet = result.sla_met 
            ? '<span class="badge bg-success">Yes</span>' 
            : '<span class="badge bg-danger">No</span>';
        document.getElementById('result-sla').innerHTML = slaMet;
        
        document.getElementById('result-cost').textContent = '$' + result.decision.final_cost.toFixed(6);
        
        const routeType = result.is_fallback 
            ? '<span class="badge bg-warning">Fallback</span>' 
            : '<span class="badge bg-success">Primary</span>';
        document.getElementById('result-route-type').innerHTML = routeType;
    }
    
    // Show considered backends
    displayConsideredBackends(result.considered_backends, result.decision.selected_backend_id);
    
    // Show filtered backends
    displayFilteredBackends(result.filtered_backends);
}

/**
 * Display the considered backends
 * @param {Array} backends - Considered backends array
 * @param {string} selectedId - ID of selected backend
 */
 function displayConsideredBackends(backends, selectedId) {
    const tableBody = document.getElementById('considered-backends-table').querySelector('tbody');
    tableBody.innerHTML = '';
    
    if (!backends || backends.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 5;
        cell.className = 'text-center py-3';
        cell.textContent = 'No backends were considered';
        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }
    
    // Calculate scores for all backends if they're not already provided
    const backendsWithScores = [...backends];
    
    // If we have the full routing result with all backend scores
    if (currentResult && currentResult.backend_scores) {
        // Use scores from the full result if available
        backendsWithScores.forEach(backend => {
            const scoreData = currentResult.backend_scores.find(s => s.backend_id === backend.id);
            if (scoreData) {
                backend.score = scoreData.score;
            }
        });
    }
    
    // Sort backends by score (ascending, lower is better)
    backendsWithScores.sort((a, b) => {
        // If score is available, sort by it
        if (a.score !== undefined && b.score !== undefined) {
            return a.score - b.score;
        }
        // Otherwise keep selected backend at the top
        if (a.id === selectedId) return -1;
        if (b.id === selectedId) return 1;
        return 0;
    });
    
    backendsWithScores.forEach(backend => {
        const row = document.createElement('tr');
        
        // Add selected-row class if this is the selected backend
        if (backend.id === selectedId) {
            row.className = 'selected-row';
        }
        
        // Backend ID
        const idCell = document.createElement('td');
        idCell.textContent = backend.id;
        row.appendChild(idCell);
        
        // Chip Type
        const chipCell = document.createElement('td');
        chipCell.textContent = backend.chip;
        row.appendChild(chipCell);
        
        // Region
        const regionCell = document.createElement('td');
        regionCell.textContent = backend.region;
        row.appendChild(regionCell);
        
        // Status
        const statusCell = document.createElement('td');
        statusCell.innerHTML = formatStatus(backend.status);
        row.appendChild(statusCell);
        
        // Score
        const scoreCell = document.createElement('td');
        // Display score if available, otherwise show "-"
        if (backend.score !== undefined) {
            scoreCell.textContent = backend.score.toFixed(6);
        } else if (backend.id === selectedId && currentResult && currentResult.decision.score) {
            scoreCell.textContent = currentResult.decision.score.toFixed(6);
        } else {
            scoreCell.textContent = '-';
        }
        row.appendChild(scoreCell);
        
        // Add to table
        tableBody.appendChild(row);
    });
}

/**
 * Display the filtered backends
 * @param {Array} backends - Filtered backends array
 */
function displayFilteredBackends(backends) {
    const tableBody = document.getElementById('filtered-backends-table').querySelector('tbody');
    tableBody.innerHTML = '';
    
    if (!backends || backends.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 4;
        cell.className = 'text-center py-3';
        cell.textContent = 'No backends were filtered out';
        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }
    
    backends.forEach(backend => {
        const row = document.createElement('tr');
        
        // Backend ID
        const idCell = document.createElement('td');
        idCell.textContent = backend.id;
        row.appendChild(idCell);
        
        // Chip Type
        const chipCell = document.createElement('td');
        chipCell.textContent = backend.chip;
        row.appendChild(chipCell);
        
        // Region
        const regionCell = document.createElement('td');
        regionCell.textContent = backend.region;
        row.appendChild(regionCell);
        
        // Reason
        const reasonCell = document.createElement('td');
        reasonCell.textContent = backend.reason;
        row.appendChild(reasonCell);
        
        // Add to table
        tableBody.appendChild(row);
    });
}


/**
 * Visualize the routing path
 * @param {Object} result - Routing result
 */
 function visualizeRoutingPath(result) {
    const container = document.getElementById('routing-path-viz');
    container.innerHTML = '';
    
    // Create the routing path visualization
    const userNode = document.createElement('div');
    userNode.className = 'routing-node node-user';
    userNode.innerHTML = `
        <h6>User</h6>
        <p>${result.request_info.user_region || document.getElementById('user-region').value}</p>
        <div class="routing-arrow"><i class="fas fa-chevron-down"></i></div>
    `;
    container.appendChild(userNode);
    
    const routerNode = document.createElement('div');
    routerNode.className = 'routing-node node-router';
    routerNode.innerHTML = `
        <h6>Tesseract Router</h6>
        <p>Global Request Routing</p>
        <div class="routing-arrow"><i class="fas fa-chevron-down"></i></div>
    `;
    container.appendChild(routerNode);
    
    if (result.decision.error) {
        // Error node
        const errorNode = document.createElement('div');
        errorNode.className = 'routing-node node-error';
        errorNode.innerHTML = `
            <h6>Error</h6>
            <p>${result.decision.error}</p>
        `;
        container.appendChild(errorNode);
    } else if (result.is_fallback) {
        // Fallback node
        const fallbackNode = document.createElement('div');
        fallbackNode.className = 'routing-node node-fallback';
        fallbackNode.innerHTML = `
            <h6>Fallback Backend</h6>
            <p>${result.decision.chip_type} in ${result.decision.region}</p>
            <div class="fallback-message">Primary failed: ${result.fallback_info.failure_reason}</div>
        `;
        container.appendChild(fallbackNode);
    } else {
        // Backend node
        const backendNode = document.createElement('div');
        backendNode.className = 'routing-node node-backend';
        backendNode.innerHTML = `
            <h6>Selected Backend</h6>
            <p>${result.decision.chip_type} in ${result.decision.region}</p>
        `;
        container.appendChild(backendNode);
    }
}

/**
 * Toggle display of filtered backends card
 */
function toggleFilteredBackends() {
    const card = document.getElementById('filtered-backends-card');
    const button = document.getElementById('toggle-filtered-btn');
    
    if (card.style.display === 'none') {
        card.style.display = 'block';
        button.textContent = 'Hide Filtered Out';
    } else {
        card.style.display = 'none';
        button.textContent = 'Show Filtered Out';
    }
}

/**
 * Simulate a batch of routing requests
 * @param {number} count - Number of requests to simulate
 */
async function simulateBatch(count) {
    // Show batch results card
    document.getElementById('batch-results-card').style.display = 'block';
    
    // Reset batch results
    batchResults = [];
    
    // Get current form values to use in batch
    const model = document.getElementById('model-select').value;
    const tokenSize = parseInt(document.getElementById('token-size').value);
    const requiredLatency = parseInt(document.getElementById('required-latency').value);
    const userRegion = document.getElementById('user-region').value;
    const priority = parseInt(document.getElementById('priority').value);
    const maxCost = document.getElementById('max-cost').value ? parseFloat(document.getElementById('max-cost').value) : null;
    const preferCost = document.getElementById('prefer-cost').checked;
    
    // Get selected compliance tags
    const complianceTags = [];
    document.querySelectorAll('.compliance-check:checked').forEach(checkbox => {
        complianceTags.push(checkbox.value);
    });
    
    // Prepare base request data
    const baseRequestData = {
        model: model,
        token_size: tokenSize,
        required_latency: requiredLatency,
        user_region: userRegion,
        compliance_tags: complianceTags,
        priority: priority,
        max_cost: maxCost,
        prefer_cost: preferCost
    };
    
    // Disable simulation buttons
    document.getElementById('simulate-5-btn').disabled = true;
    document.getElementById('simulate-20-btn').disabled = true;
    
    // Simulate routes
    let successCount = 0;
    let fallbackCount = 0;
    let failedCount = 0;
    let slaMet = 0;
    let totalLatency = 0;
    let validLatencyCount = 0;
    
    for (let i = 0; i < count; i++) {
        // Create a copy of the base request
        const requestData = { ...baseRequestData };
        
        // Add random variation to some parameters
        requestData.token_size = Math.max(100, Math.min(32000, tokenSize + Math.floor(Math.random() * 2000 - 1000)));
        
        // 30% chance of simulating failure
        requestData.simulate_failure = Math.random() < 0.3;
        
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
            
            // Track statistics
            if (result.decision.error) {
                failedCount++;
            } else if (result.is_fallback) {
                fallbackCount++;
                if (result.sla_met) {
                    slaMet++;
                }
                
                totalLatency += result.decision.final_latency_ms;
                validLatencyCount++;
            } else {
                successCount++;
                if (result.sla_met) {
                    slaMet++;
                }
                
                totalLatency += result.decision.final_latency_ms;
                validLatencyCount++;
            }
            
            // Add to batch results
            batchResults.push(result);
            
            // Update chart after each result
            updateBatchResultsChart();
            
        } catch (error) {
            console.error('Error in batch simulation:', error);
            failedCount++;
        }
        
        // Small delay to prevent UI freezing
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Update summary statistics
    document.getElementById('batch-total').textContent = count;
    document.getElementById('batch-success').textContent = successCount;
    document.getElementById('batch-fallback').textContent = fallbackCount;
    document.getElementById('batch-failed').textContent = failedCount;
    
    const slaPercentage = count > 0 ? Math.round((slaMet / count) * 100) : 0;
    document.getElementById('batch-sla-met').textContent = `${slaMet}/${count} (${slaPercentage}%)`;
    
    const avgLatency = validLatencyCount > 0 ? Math.round(totalLatency / validLatencyCount) : 0;
    document.getElementById('batch-avg-latency').textContent = `${avgLatency} ms`;
    
    // Re-enable simulation buttons
    document.getElementById('simulate-5-btn').disabled = false;
    document.getElementById('simulate-20-btn').disabled = false;
}

/**
 * Update the batch results chart
 */
function updateBatchResultsChart() {
    const ctx = document.getElementById('batch-results-chart').getContext('2d');
    
    // Calculate counts
    const successCount = batchResults.filter(r => !r.decision.error && !r.is_fallback).length;
    const fallbackCount = batchResults.filter(r => !r.decision.error && r.is_fallback).length;
    const failedCount = batchResults.filter(r => r.decision.error).length;
    
    // Clean up previous chart if it exists
    if (batchResultsChart) {
        batchResultsChart.destroy();
    }
    
    // Create chart
    batchResultsChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Success', 'Fallback', 'Failed'],
            datasets: [{
                data: [successCount, fallbackCount, failedCount],
                backgroundColor: ['#2ecc71', '#f39c12', '#e74c3c'],
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
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
            cutout: '40%',
            animation: {
                animateScale: true
            }
        }
    });
}

// Initialize simulator when DOM is loaded
document.addEventListener('DOMContentLoaded', initSimulator);