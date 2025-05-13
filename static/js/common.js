/**
 * Common JavaScript utilities for Tesseract Router application
 */

// Global Constants
const STATUS_COLORS = {
    healthy: '#2ecc71',
    degraded: '#f39c12',
    down: '#e74c3c'
};

// Global Variables
let globalBackends = [];
let globalLatencyMap = {};
let globalModels = [];
let globalComplianceTags = [];

/**
 * Format status with colored badge
 * @param {string} status - Backend status
 * @returns {string} HTML for status badge
 */
function formatStatus(status) {
    const statusColors = {
        'healthy': 'success',
        'degraded': 'warning',
        'down': 'danger'
    };
    
    const color = statusColors[status] || 'secondary';
    const icon = status === 'healthy' ? 'check-circle' : (status === 'degraded' ? 'exclamation-triangle' : 'times-circle');
    
    return `<span class="badge bg-${color}"><i class="fas fa-${icon} me-1"></i>${status.charAt(0).toUpperCase() + status.slice(1)}</span>`;
}

/**
 * Format a backend load as a progress bar
 * @param {number} load - Load percentage
 * @returns {string} HTML for load progress bar
 */
function formatLoadBar(load) {
    let colorClass = 'bg-success';
    if (load > 80) {
        colorClass = 'bg-danger';
    } else if (load > 60) {
        colorClass = 'bg-warning';
    }
    
    return `
        <div class="progress" style="height: 8px;">
            <div class="progress-bar ${colorClass}" role="progressbar" style="width: ${load}%" 
                aria-valuenow="${load}" aria-valuemin="0" aria-valuemax="100"></div>
        </div>
        <div class="small text-muted mt-1">${load.toFixed(1)}%</div>
    `;
}

/**
 * Format a cost value in USD
 * @param {number} cost - Cost value
 * @returns {string} Formatted cost
 */
function formatCost(cost) {
    return `$${cost.toFixed(6)}`;
}

/**
 * Format a latency value in milliseconds
 * @param {number} latency - Latency in milliseconds
 * @returns {string} Formatted latency
 */
function formatLatency(latency) {
    return `${latency} ms`;
}

/**
 * Get color for latency based on value
 * @param {number} latency - Latency in milliseconds
 * @returns {string} CSS color
 */
function getLatencyColor(latency) {
    if (latency < 50) {
        return '#2ecc71'; // green
    } else if (latency < 150) {
        return '#f39c12'; // orange
    } else {
        return '#e74c3c'; // red
    }
}

/**
 * Truncate a string to a maximum length with ellipsis
 * @param {string} str - String to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated string
 */
function truncateString(str, maxLength) {
    if (str.length <= maxLength) {
        return str;
    }
    return str.slice(0, maxLength) + '...';
}

/**
 * Fetch all backends data
 * @returns {Promise<Array>} Array of backend objects
 */
async function fetchBackends() {
    try {
        const response = await fetch('/api/backends');
        const data = await response.json();
        globalBackends = data;
        return data;
    } catch (error) {
        console.error('Error fetching backends:', error);
        return [];
    }
}

/**
 * Fetch the latency map
 * @returns {Promise<Object>} Latency map
 */
async function fetchLatencyMap() {
    try {
        const response = await fetch('/api/latency-map');
        const data = await response.json();
        globalLatencyMap = data;
        return data;
    } catch (error) {
        console.error('Error fetching latency map:', error);
        return {};
    }
}

/**
 * Extract all unique models from backends
 * @param {Array} backends - Array of backend objects
 * @returns {Array} Array of unique model names
 */
function extractModels(backends) {
    const models = new Set();
    backends.forEach(backend => {
        backend.supported_models.forEach(model => {
            models.add(model);
        });
    });
    return Array.from(models).sort();
}

/**
 * Extract all unique compliance tags from backends
 * @param {Array} backends - Array of backend objects
 * @returns {Array} Array of unique compliance tags
 */
function extractComplianceTags(backends) {
    const tags = new Set();
    backends.forEach(backend => {
        backend.compliance_tags.forEach(tag => {
            tags.add(tag);
        });
    });
    return Array.from(tags).sort();
}

/**
 * Get network latency between regions
 * @param {string} fromRegion - Source region
 * @param {string} toRegion - Destination region
 * @returns {number} Latency in milliseconds
 */
function getNetworkLatency(fromRegion, toRegion) {
    if (!globalLatencyMap || !globalLatencyMap[fromRegion]) {
        return 150; // Default high latency if map not available
    }
    
    return globalLatencyMap[fromRegion][toRegion] || 150;
}

/**
 * Generate a random color
 * @returns {string} Random hex color
 */
function getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
}

/**
 * Get chip-specific color (consistent for same chip types)
 * @param {string} chipType - Chip type name
 * @returns {string} Hex color
 */
function getChipColor(chipType) {
    // Define standard colors for common chip types
    const chipColors = {
        'NVIDIA H100': '#76b900', // NVIDIA green
        'NVIDIA A100': '#76b900',
        'NVIDIA L40S': '#76b900',
        'Google TPU': '#4285f4', // Google blue
        'Groq LPU': '#ff6b6b', // Reddish
        'Cerebras CS-2': '#ffa726', // Orange
        'AWS Inferentia': '#ff9900', // AWS orange
        'Azure Maia': '#00a4ef', // Azure blue
        'SambaNova': '#6b5b95', // Purple
        'Intel Gaudi': '#0071c5', // Intel blue
        'Graphcore IPU': '#e91e63', // Pink
    };
    
    // Check for partial matches
    for (const [key, color] of Object.entries(chipColors)) {
        if (chipType.includes(key)) {
            return color;
        }
    }
    
    // Use hash-based color for unknown chip types (consistent for same name)
    let hash = 0;
    for (let i = 0; i < chipType.length; i++) {
        hash = chipType.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    let color = '#';
    for (let i = 0; i < 3; i++) {
        const value = (hash >> (i * 8)) & 0xFF;
        color += ('00' + value.toString(16)).substr(-2);
    }
    
    return color;
}

/**
 * Get region coordinates for map visualization
 * @param {string} region - Region code
 * @returns {Object} Coordinates {lat, lng}
 */
function getRegionCoordinates(region) {
    const regionCoords = {
        'us-east-1': { lat: 38.13, lng: -78.45 },
        'us-east-2': { lat: 40.42, lng: -83.77 },
        'us-west-1': { lat: 37.77, lng: -122.41 },
        'us-west-2': { lat: 46.15, lng: -123.88 },
        'us-central1': { lat: 41.26, lng: -95.86 },
        'eu-west-1': { lat: 53.35, lng: -6.26 },
        'eu-central-1': { lat: 50.11, lng: 8.68 },
        'ap-northeast-1': { lat: 35.68, lng: 139.76 },
        'ap-southeast-1': { lat: 1.35, lng: 103.86 },
        'ap-southeast-2': { lat: -33.87, lng: 151.2 },
        'ap-south-1': { lat: 19.07, lng: 72.87 },
        'sa-east-1': { lat: -23.55, lng: -46.63 },
        'me-south-1': { lat: 25.3, lng: 51.52 },
        'global': { lat: 30, lng: 0 }
    };
    
    return regionCoords[region] || { lat: 0, lng: 0 };
}

/**
 * Initialize common data needed across pages
 */
async function initCommonData() {
    // Fetch backends and latency data
    await Promise.all([
        fetchBackends(),
        fetchLatencyMap()
    ]);
    
    // Extract models and compliance tags
    globalModels = extractModels(globalBackends);
    globalComplianceTags = extractComplianceTags(globalBackends);
}

// Initialize data on page load
document.addEventListener('DOMContentLoaded', initCommonData);