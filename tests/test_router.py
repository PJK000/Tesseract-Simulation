#!/usr/bin/env python3
"""
Test suite for the Tesseract AI Inference Router.

This module contains unit tests for the core routing functionality.
It tests various scenarios including backend filtering, scoring, and fallback mechanisms.

Usage:
    python -m unittest tests/test_router.py
"""

import unittest
import json
import tempfile
from typing import Dict, List, Set

# Import the modules to test
from tesseract_router import (
    InferenceRequest, 
    Backend, 
    RoutingResult, 
    BackendStatus, 
    BackendFilter, 
    BackendScorer, 
    TesseractRouter
)


class TestInferenceRequest(unittest.TestCase):
    """Test the InferenceRequest class."""
    
    def test_from_dict(self):
        """Test creating an InferenceRequest from a dictionary."""
        test_data = {
            "model_name": "test-model",
            "input_token_size": 100,
            "required_latency_ms": 200,
            "compliance_constraints": ["gdpr", "hipaa"],
            "unique_id": "test-id",
            "priority": 2
        }
        
        request = InferenceRequest.from_dict(test_data)
        
        self.assertEqual(request.model_name, "test-model")
        self.assertEqual(request.input_token_size, 100)
        self.assertEqual(request.required_latency_ms, 200)
        self.assertEqual(request.compliance_constraints, {"gdpr", "hipaa"})
        self.assertEqual(request.unique_id, "test-id")
        self.assertEqual(request.priority, 2)
    
    def test_default_values(self):
        """Test default values in InferenceRequest."""
        test_data = {
            "model_name": "test-model",
            "input_token_size": 100,
            "required_latency_ms": 200,
            "compliance_constraints": []
        }
        
        request = InferenceRequest.from_dict(test_data)
        
        self.assertEqual(request.compliance_constraints, set())
        self.assertTrue(request.unique_id.startswith("req_"))
        self.assertEqual(request.priority, 1)


class TestBackend(unittest.TestCase):
    """Test the Backend class."""
    
    def test_from_dict(self):
        """Test creating a Backend from a dictionary."""
        test_data = {
            "backend_id": "test-backend",
            "chip_type": "test-chip",
            "latency_ms": 100,
            "cost_per_token": 0.001,
            "region": "test-region",
            "supported_models": ["model1", "model2"],
            "status": "healthy",
            "compliance_tags": ["gdpr", "hipaa"],
            "max_token_size": 1000
        }
        
        backend = Backend.from_dict(test_data)
        
        self.assertEqual(backend.backend_id, "test-backend")
        self.assertEqual(backend.chip_type, "test-chip")
        self.assertEqual(backend.latency_ms, 100)
        self.assertEqual(backend.cost_per_token, 0.001)
        self.assertEqual(backend.region, "test-region")
        self.assertEqual(backend.supported_models, ["model1", "model2"])
        self.assertEqual(backend.status, BackendStatus.HEALTHY)
        self.assertEqual(backend.compliance_tags, {"gdpr", "hipaa"})
        self.assertEqual(backend.max_token_size, 1000)
    
    def test_status_conversion(self):
        """Test conversion of status strings to BackendStatus enum."""
        self.assertEqual(BackendStatus.from_str("healthy"), BackendStatus.HEALTHY)
        self.assertEqual(BackendStatus.from_str("HEALTHY"), BackendStatus.HEALTHY)
        self.assertEqual(BackendStatus.from_str("degraded"), BackendStatus.DEGRADED)
        self.assertEqual(BackendStatus.from_str("down"), BackendStatus.DOWN)
        self.assertEqual(BackendStatus.from_str("invalid"), BackendStatus.DOWN)  # Default for invalid


class TestBackendFilter(unittest.TestCase):
    """Test the BackendFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.request = InferenceRequest(
            model_name="test-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr", "hipaa"}
        )
        
        self.healthy_backend = Backend(
            backend_id="test-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model", "other-model"],
            status=BackendStatus.HEALTHY,
            compliance_tags={"gdpr", "hipaa", "sox"},
            max_token_size=2000
        )
        
        self.degraded_backend = Backend(
            backend_id="degraded-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DEGRADED,
            compliance_tags={"gdpr", "hipaa"},
            max_token_size=2000
        )
    
    def test_filter_by_status(self):
        """Test filtering by status."""
        self.assertIsNone(BackendFilter.filter_by_status(self.healthy_backend))
        self.assertIsNone(BackendFilter.filter_by_status(self.degraded_backend))
        
        down_backend = Backend(
            backend_id="down-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DOWN,
            compliance_tags={"gdpr", "hipaa"},
            max_token_size=2000
        )
        
        self.assertEqual(BackendFilter.filter_by_status(down_backend), "Backend is down")
    
    def test_filter_by_model(self):
        """Test filtering by model compatibility."""
        self.assertIsNone(BackendFilter.filter_by_model(self.healthy_backend, self.request))
        
        unsupported_model_request = InferenceRequest(
            model_name="unsupported-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr"}
        )
        
        self.assertEqual(
            BackendFilter.filter_by_model(self.healthy_backend, unsupported_model_request),
            "Model unsupported-model not supported"
        )
    
    def test_filter_by_token_size(self):
        """Test filtering by token size limits."""
        self.assertIsNone(BackendFilter.filter_by_token_size(self.healthy_backend, self.request))
        
        large_request = InferenceRequest(
            model_name="test-model",
            input_token_size=3000,  # Larger than backend limit
            required_latency_ms=200,
            compliance_constraints={"gdpr"}
        )
        
        self.assertEqual(
            BackendFilter.filter_by_token_size(self.healthy_backend, large_request),
            "Token size exceeds backend limit"
        )
    
    def test_filter_by_compliance(self):
        """Test filtering by compliance requirements."""
        self.assertIsNone(BackendFilter.filter_by_compliance(self.healthy_backend, self.request))
        
        strict_request = InferenceRequest(
            model_name="test-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr", "hipaa", "additional-tag"}
        )
        
        self.assertTrue(
            BackendFilter.filter_by_compliance(self.healthy_backend, strict_request).startswith(
                "Missing compliance tags:"
            )
        )
    
    def test_filter_by_latency(self):
        """Test filtering by latency requirements."""
        self.assertIsNone(BackendFilter.filter_by_latency(self.healthy_backend, self.request))
        
        # Test with a degraded backend
        slow_degraded_backend = Backend(
            backend_id="slow-degraded",
            chip_type="test-chip",
            latency_ms=150,  # 150 * 1.5 = 225, which exceeds required 200ms
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DEGRADED,
            compliance_tags={"gdpr", "hipaa"},
            max_token_size=2000
        )
        
        self.assertEqual(
            BackendFilter.filter_by_latency(slow_degraded_backend, self.request),
            "Degraded performance exceeds latency SLA"
        )
        
        # Test with a healthy but slow backend
        slow_healthy_backend = Backend(
            backend_id="slow-healthy",
            chip_type="test-chip",
            latency_ms=250,  # Exceeds required 200ms
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.HEALTHY,
            compliance_tags={"gdpr", "hipaa"},
            max_token_size=2000
        )
        
        self.assertEqual(
            BackendFilter.filter_by_latency(slow_healthy_backend, self.request),
            "Latency exceeds SLA"
        )
    
    def test_apply_filters(self):
        """Test applying all filters at once."""
        # Should pass all filters
        self.assertIsNone(BackendFilter.apply_filters(self.healthy_backend, self.request))
        
        # Create a backend that will fail multiple filters
        bad_backend = Backend(
            backend_id="bad-backend",
            chip_type="test-chip",
            latency_ms=300,  # Exceeds required 200ms
            cost_per_token=0.001,
            region="test-region",
            supported_models=["other-model"],  # Doesn't support test-model
            status=BackendStatus.HEALTHY,
            compliance_tags={"gdpr"},  # Missing hipaa tag
            max_token_size=500  # Too small for request
        )
        
        # It should return the first failure reason it encounters
        failure_reason = BackendFilter.apply_filters(bad_backend, self.request)
        self.assertIsNotNone(failure_reason)
        # The exact reason depends on the order of filters, but it should be one of:
        possible_reasons = [
            "Model test-model not supported",
            "Token size exceeds backend limit",
            "Missing compliance tags:",
            "Latency exceeds SLA"
        ]
        self.assertTrue(any(failure_reason.startswith(reason) for reason in possible_reasons))


class TestBackendScorer(unittest.TestCase):
    """Test the BackendScorer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.request = InferenceRequest(
            model_name="test-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr"},
            priority=1
        )
        
        self.backend = Backend(
            backend_id="test-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.HEALTHY,
            compliance_tags={"gdpr"},
            max_token_size=2000
        )
    
    def test_calculate_base_score(self):
        """Test calculation of base score."""
        # Base score = latency_ms * cost_per_token
        expected_score = 100 * 0.001
        self.assertEqual(BackendScorer.calculate_base_score(self.backend, self.request), expected_score)
    
    def test_apply_health_adjustment(self):
        """Test adjustment based on backend health."""
        base_score = 0.1
        
        # Healthy backend - no adjustment
        self.assertEqual(BackendScorer.apply_health_adjustment(base_score, self.backend), base_score)
        
        # Degraded backend - 50% penalty
        degraded_backend = Backend(
            backend_id="degraded-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DEGRADED,
            compliance_tags={"gdpr"},
            max_token_size=2000
        )
        self.assertEqual(BackendScorer.apply_health_adjustment(base_score, degraded_backend), base_score * 1.5)
        
        # Down backend - infinite score
        down_backend = Backend(
            backend_id="down-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DOWN,
            compliance_tags={"gdpr"},
            max_token_size=2000
        )
        self.assertEqual(BackendScorer.apply_health_adjustment(base_score, down_backend), float('inf'))
    
    def test_apply_priority_adjustment(self):
        """Test adjustment based on request priority."""
        base_score = 0.1
        
        # Priority 1 (highest) - no adjustment
        self.assertEqual(BackendScorer.apply_priority_adjustment(base_score, self.request), base_score)
        
        # Priority 2 - 50% penalty
        lower_priority_request = InferenceRequest(
            model_name="test-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr"},
            priority=2
        )
        self.assertEqual(
            BackendScorer.apply_priority_adjustment(base_score, lower_priority_request), 
            base_score * 0.5
        )
    
    def test_score_backend(self):
        """Test the overall scoring logic."""
        # For a healthy backend and priority 1 request, the score should be latency_ms * cost_per_token
        expected_score = 100 * 0.001
        self.assertEqual(BackendScorer.score_backend(self.backend, self.request), expected_score)
        
        # For a degraded backend, the score should have a 50% penalty
        degraded_backend = Backend(
            backend_id="degraded-backend",
            chip_type="test-chip",
            latency_ms=100,
            cost_per_token=0.001,
            region="test-region",
            supported_models=["test-model"],
            status=BackendStatus.DEGRADED,
            compliance_tags={"gdpr"},
            max_token_size=2000
        )
        self.assertEqual(
            BackendScorer.score_backend(degraded_backend, self.request), 
            expected_score * 1.5
        )
        
        # For a lower priority request, the score should reflect the priority adjustment
        lower_priority_request = InferenceRequest(
            model_name="test-model",
            input_token_size=1000,
            required_latency_ms=200,
            compliance_constraints={"gdpr"},
            priority=2
        )
        self.assertEqual(
            BackendScorer.score_backend(self.backend, lower_priority_request), 
            expected_score * 0.5
        )


class TestTesseractRouter(unittest.TestCase):
    """Test the TesseractRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary backends file
        self.temp_backends_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        
        # Define some test backends
        self.test_backends = [
            {
                "backend_id": "backend1",
                "chip_type": "GPU",
                "latency_ms": 100,
                "cost_per_token": 0.001,
                "region": "us-east",
                "supported_models": ["model1", "model2"],
                "status": "healthy",
                "compliance_tags": ["gdpr", "hipaa"],
                "max_token_size": 2000
            },
            {
                "backend_id": "backend2",
                "chip_type": "TPU",
                "latency_ms": 80,
                "cost_per_token": 0.002,
                "region": "us-west",
                "supported_models": ["model1"],
                "status": "healthy",
                "compliance_tags": ["gdpr"],
                "max_token_size": 1000
            },
            {
                "backend_id": "backend3",
                "chip_type": "CPU",
                "latency_ms": 200,
                "cost_per_token": 0.0005,
                "region": "eu-west",
                "supported_models": ["model1", "model2"],
                "status": "degraded",
                "compliance_tags": ["gdpr", "hipaa", "sox"],
                "max_token_size": 5000
            }
        ]
        
        # Write backends to the temporary file
        json.dump(self.test_backends, self.temp_backends_file)
        self.temp_backends_file.flush()
        
        # Create a router with the temporary backends file
        self.router = TesseractRouter(self.temp_backends_file.name)
        
        # Define a test request
        self.request = InferenceRequest(
            model_name="model1",
            input_token_size=500,
            required_latency_ms=150,
            compliance_constraints={"gdpr"}
        )
    
    def tearDown(self):
        """Clean up after tests."""
        import os
        os.unlink(self.temp_backends_file.name)
    
    def test_load_backends(self):
        """Test loading backends from a file."""
        self.assertEqual(len(self.router.backends), 3)
        self.assertEqual(self.router.backends[0].backend_id, "backend1")
        self.assertEqual(self.router.backends[1].backend_id, "backend2")
        self.assertEqual(self.router.backends[2].backend_id, "backend3")
    
    def test_filter_compatible_backends(self):
        """Test filtering compatible backends."""
        compatible, filtered_out = self.router._filter_compatible_backends(self.request)
        
        # Only backend1 and backend2 should be compatible
        # backend3 is degraded and has latency issues
        self.assertEqual(len(compatible), 2)
        self.assertEqual(compatible[0].backend_id, "backend1")
        self.assertEqual(compatible[1].backend_id, "backend2")
        
        self.assertEqual(len(filtered_out), 1)
        self.assertEqual(filtered_out[0]["backend"].backend_id, "backend3")
    
    def test_score_backends(self):
        """Test scoring backends."""
        compatible, _ = self.router._filter_compatible_backends(self.request)
        scored = self.router._score_backends(self.request, compatible)
        
        # Verify that backends are scored correctly
        # backend1: 100 * 0.001 = 0.1
        # backend2: 80 * 0.002 = 0.16
        # backend1 should have a better (lower) score
        self.assertEqual(len(scored), 2)
        self.assertEqual(scored[0][0].backend_id, "backend1")
        self.assertEqual(scored[1][0].backend_id, "backend2")
    
    def test_route_request(self):
        """Test routing a request to the best backend."""
        result = self.router.route_request(self.request)
        
        # Verify that the best backend is selected
        self.assertIsNotNone(result.selected_backend)
        self.assertEqual(result.selected_backend.backend_id, "backend1")
        
        # Verify that the result contains the expected metadata
        self.assertEqual(result.request, self.request)
        self.assertEqual(result.final_latency_ms, 100)
        self.assertEqual(result.final_cost, 100 * 0.001 * 500)  # latency * cost_per_token * input_token_size
        self.assertFalse(result.is_fallback)
    
    def test_handle_backend_failure(self):
        """Test handling a backend failure."""
        # First route to get a result
        result = self.router.route_request(self.request)
        
        # Now simulate a failure of the selected backend
        fallback_result = self.router.handle_backend_failure(result, "Test failure")
        
        # Verify that a fallback backend was selected
        self.assertIsNotNone(fallback_result.selected_backend)
        self.assertEqual(fallback_result.selected_backend.backend_id, "backend2")
        
        # Verify that the fallback metadata is correct
        self.assertTrue(fallback_result.is_fallback)
        self.assertEqual(fallback_result.original_backend, result.selected_backend)
        self.assertEqual(fallback_result.fallback_reason, "Test failure")
    
    def test_update_backend_status(self):
        """Test updating backend status."""
        # Verify initial status
        self.assertEqual(self.router.backends[0].status, BackendStatus.HEALTHY)
        
        # Update status to degraded
        success = self.router.update_backend_status("backend1", "degraded")
        
        # Verify the update was successful
        self.assertTrue(success)
        self.assertEqual(self.router.backends[0].status, BackendStatus.DEGRADED)
        
        # Try to update a non-existent backend
        success = self.router.update_backend_status("nonexistent", "healthy")
        
        # Verify the update failed
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()