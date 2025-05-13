#!/usr/bin/env python3
"""
Tesseract AI Inference Router - Flask Web Application

This is the main Flask application that serves the Tesseract Router web interface.
It provides a visual dashboard to demonstrate the routing capabilities described
in the Tesseract whitepaper.
"""

import os
import json
import random
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory

# Import Tesseract router components
from tesseract_router import (
    TesseractRouter, 
    InferenceRequest, 
    BackendStatus, 
    load_all_requests
)

# Initialize the Flask application
app = Flask(__name__) 
app.config['SECRET_KEY'] = 'tesseract-demo-secret-key'

# Set up the router with initial configuration
router = TesseractRouter(
    backends_file="models/backends.json",
    latency_file="configs/latency_map.json"
)

# Global variables to store recent routing results for the dashboard
recent_routes = []
MAX_RECENT_ROUTES = 5


def get_all_available_models():
    """Get a list of all unique models supported by at least one backend."""
    models = set()
    for backend in router.backends:
        models.update(backend.supported_models)
    return sorted(list(models))


def get_all_available_compliance_tags():
    """Get a list of all unique compliance tags across backends."""
    tags = set()
    for backend in router.backends:
        tags.update(backend.compliance_tags)
    return sorted(list(tags))


def get_all_available_regions():
    """Get a list of all unique regions where backends are deployed."""
    regions = set()
    for backend in router.backends:
        regions.add(backend.region)
    
    # Also include regions from latency map
    for region in router.network_latency.latency_map:
        regions.add(region)
    
    return sorted(list(regions))


def get_chip_type_distribution():
    """Get the distribution of chip types across the system."""
    chip_types = {}
    for backend in router.backends:
        chip_type = backend.chip_type
        if chip_type in chip_types:
            chip_types[chip_type] += 1
        else:
            chip_types[chip_type] = 1
    
    return chip_types


def get_region_chip_distribution():
    """Get the distribution of chips by region."""
    distribution = {}
    
    for backend in router.backends:
        region = backend.region
        chip_type = backend.chip_type
        
        if region not in distribution:
            distribution[region] = {}
        
        if chip_type in distribution[region]:
            distribution[region][chip_type] += 1
        else:
            distribution[region][chip_type] = 1
    
    return distribution


def get_backend_health_by_region():
    """Get backend health statistics grouped by region."""
    health_by_region = {}
    
    for backend in router.backends:
        region = backend.region
        status = str(backend.status)
        
        if region not in health_by_region:
            health_by_region[region] = {
                "healthy": 0,
                "degraded": 0,
                "down": 0,
                "total": 0
            }
        
        health_by_region[region][status] += 1
        health_by_region[region]["total"] += 1
    
    return health_by_region



@app.route('/')
def home():
    """Render the homepage."""
    return render_template('home.html', 
                         router_stats=router.get_global_routing_stats(),
                         models=get_all_available_models(),
                         regions=get_all_available_regions(),
                         compliance_tags=get_all_available_compliance_tags())


@app.route('/index')
def index():
    """Render the main dashboard page."""
    return render_template('index.html', 
                         router_stats=router.get_global_routing_stats(),
                         models=get_all_available_models(),
                         regions=get_all_available_regions(),
                         compliance_tags=get_all_available_compliance_tags(),
                         recent_routes=recent_routes)


@app.route('/api/dashboard-data')
def dashboard_data():
    """API endpoint to get dashboard data for the frontend."""
    return jsonify({
        'router_stats': router.get_global_routing_stats(),
        'chip_distribution': get_chip_type_distribution(),
        'region_chip_distribution': get_region_chip_distribution(),
        'backend_health_by_region': get_backend_health_by_region(),
        'recent_routes': [route.to_dict() for route in recent_routes]
    })


@app.route('/api/backends')
def get_backends():
    """API endpoint to get all backends data."""
    backends_data = []
    for backend in router.backends:
        backends_data.append({
            'id': backend.backend_id,
            'backend_id': backend.backend_id,  # Adding both formats for compatibility
            'chip_type': backend.chip_type,
            'region': backend.region,
            'status': str(backend.status),
            'latency_ms': backend.latency_ms,
            'cost_per_token': backend.cost_per_token,
            'supported_models': backend.supported_models,
            'compliance_tags': list(backend.compliance_tags),
            'max_token_size': backend.max_token_size,
            'current_load': backend.current_load,
            'estimated_queue_time_ms': backend.estimated_queue_time_ms
        })
    
    return jsonify(backends_data)


@app.route('/api/latency-map')
def get_latency_map():
    """API endpoint to get the network latency map."""
    return jsonify(router.network_latency.latency_map)


@app.route('/api/route-request', methods=['POST'])
def route_request():
    """API endpoint to route an inference request."""
    data = request.json
    
    # Create an inference request from the form data
    req = InferenceRequest(
        model_name=data.get('model', ''),
        input_token_size=int(data.get('token_size', 1000)),
        required_latency_ms=int(data.get('required_latency', 200)),
        compliance_constraints=set(data.get('compliance_tags', [])),
        priority=int(data.get('priority', 1)),
        max_cost=float(data.get('max_cost')) if data.get('max_cost') else None,
        prefer_cost_over_latency=data.get('prefer_cost', False)
    )
    
    # Route the request
    user_region = data.get('user_region', 'us-east-1')
    result = router.route_request(req, user_region)
    
    # Simulate failure if requested
    if data.get('simulate_failure', False) and result.selected_backend:
        failure_reasons = [
            "Backend connection timeout",
            "Model not supported for the given input shape",
            "Backend capacity exceeded",
            "Rate limit reached",
            "Internal backend error"
        ]
        failure_reason = random.choice(failure_reasons)
        result = router.handle_backend_failure(result, failure_reason, user_region)
    
    # Add to recent routes
    global recent_routes
    recent_routes.insert(0, result)
    if len(recent_routes) > MAX_RECENT_ROUTES:
        recent_routes.pop()
    
    # Get the result dictionary
    result_dict = result.to_dict()
    
    # Get all scores from the result's considered_backends
    # The TesseractRouter._score_backends method already has this information
    # We just need to access it from the result object
    backend_scores = []
    
    # Extract scores from the original scoring result if available (in router._score_backends)
    # If not, we'll use a more simplified approach
    if hasattr(router, '_last_scoring_result') and router._last_scoring_result:
        for backend, score, latency, cost in router._last_scoring_result:
            backend_scores.append({
                "backend_id": backend.backend_id,
                "score": score
            })
    else:
        # Simplified scoring calculation - not as accurate as the router's internal score
        # but adequate for demonstration purposes
        for backend in result.considered_backends:
            # Simple score based on latency and cost
            network_latency = router.network_latency.get_latency(user_region, backend.region)
            base_score = backend.latency_ms * backend.cost_per_token
            
            # Adjustments
            if backend.status == BackendStatus.DEGRADED:
                base_score *= 1.5
            
            # Load adjustment
            load_factor = 1 + (backend.current_load / 100)
            adjusted_score = base_score * load_factor
            
            backend_scores.append({
                "backend_id": backend.backend_id,
                "score": adjusted_score
            })
    
    # Add backend scores to the result dictionary
    result_dict["backend_scores"] = backend_scores
    
    return jsonify(result_dict)


@app.route('/api/update-backend', methods=['POST'])
def update_backend():
    """API endpoint to update a backend's status."""
    data = request.json
    backend_id = data.get('backend_id')
    new_status = data.get('status')
    
    if backend_id and new_status:
        router.update_backend_status(backend_id, new_status)
        
        # Also update load if provided
        if 'load' in data:
            try:
                load = float(data.get('load', 50))
                queue_time = int(load * 0.5)  # Simple estimation
                router.update_backend_load(backend_id, load, queue_time)
            except:
                pass
        
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Missing required parameters'})


@app.route('/api/simulate-fluctuation', methods=['POST'])
def simulate_fluctuation():
    """API endpoint to simulate random fluctuations in backend status."""
    changes = router.simulate_backend_degradation()
    
    # Format changes for response
    formatted_changes = []
    for backend_id, old_status, new_status in changes:
        formatted_changes.append({
            'backend_id': backend_id,
            'old_status': old_status,
            'new_status': new_status
        })
    
    return jsonify({
        'success': True,
        'changes': formatted_changes
    })


@app.route('/api/recommend-backends', methods=['POST'])
def recommend_backends():
    """API endpoint to get routing recommendations."""
    data = request.json
    
    model_name = data.get('model', '')
    required_latency_ms = int(data.get('required_latency', 200))
    compliance_constraints = data.get('compliance_tags', [])
    from_region = data.get('user_region', 'us-east-1')
    
    recommendations = router.get_routing_recommendations(
        model_name=model_name,
        required_latency_ms=required_latency_ms,
        compliance_constraints=compliance_constraints,
        from_region=from_region
    )
    
    return jsonify(recommendations)


@app.route('/api/region-stats')
def get_region_stats():
    """API endpoint to get statistics by region."""
    region_stats = router.get_region_stats()
    return jsonify(region_stats)


# Additional routes
@app.route('/map')
def map_view():
    """Render the global backend map visualization."""
    return render_template('map.html', 
                         regions=get_all_available_regions(),
                         router_stats=router.get_global_routing_stats())


@app.route('/simulator')
def simulator():
    """Render the routing simulator page."""
    return render_template('simulator.html',
                         models=get_all_available_models(),
                         regions=get_all_available_regions(),
                         compliance_tags=get_all_available_compliance_tags())


@app.route('/dashboard')
def dashboard():
    """Render the system health dashboard."""
    return render_template('dashboard.html')


@app.route('/latency-viz')
def latency_viz():
    """Render the latency visualization page."""
    return render_template('latency-viz.html',
                         regions=get_all_available_regions())


@app.route('/whitepaper')
def whitepaper():
    """Render the whitepaper page."""
    return render_template('whitepaper.html')


@app.route('/download_whitepaper')
def download_whitepaper():
    """Download the whitepaper PDF."""
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'docs'),
        'tesseract_whitepaper.pdf',
        as_attachment=True
    )



if __name__ == '__main__':
    # Ensure the required directories exist
    os.makedirs("models", exist_ok=True)
    os.makedirs("configs", exist_ok=True)
    os.makedirs(os.path.join("static", "docs"), exist_ok=True)
    
    # Start the Flask application
    app.run(debug=True, host='0.0.0.0', port=5000)