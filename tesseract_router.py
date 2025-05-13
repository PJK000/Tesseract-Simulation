"""
Tesseract AI Inference Router

A chip-agnostic, latency-aware routing layer for real-time AI inference that intelligently 
routes inference requests to the most appropriate hardware backend based on:
- Latency requirements (SLA)
- Compliance constraints (data residency, regulatory requirements)
- Model compatibility
- Cost efficiency
- Backend health

The router dynamically selects the optimal backend based on these factors, making 
the "silicon choice" transparently and providing fallback mechanisms when needed.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, TypedDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TesseractRouter")


class BackendStatus(Enum):
    """Status of a backend hardware instance."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    
    @classmethod
    def from_str(cls, status_str: str) -> 'BackendStatus':
        """Convert a string to a BackendStatus enum."""
        mapping = {
            "healthy": cls.HEALTHY,
            "degraded": cls.DEGRADED,
            "down": cls.DOWN
        }
        return mapping.get(status_str.lower(), cls.DOWN)
    
    def __str__(self) -> str:
        return self.value


# Define data classes for type safety
@dataclass
class InferenceRequest:
    """
    Represents an AI model inference request to be routed to an appropriate backend.
    
    Attributes:
        model_name: Name of the AI model to use
        input_token_size: Size of the input in tokens
        required_latency_ms: Maximum acceptable latency in milliseconds (SLA)
        compliance_constraints: Set of compliance requirements (e.g., "gdpr", "hipaa")
        unique_id: Unique identifier for the request
        priority: Priority level (1-5, with 1 being highest)
        max_cost: Optional maximum cost per request (in USD)
        prefer_cost_over_latency: If True, prioritize cost savings over minimal latency
    """
    model_name: str
    input_token_size: int
    required_latency_ms: int
    compliance_constraints: Set[str]
    unique_id: str = field(default_factory=lambda: f"req_{int(time.time())}")
    priority: int = 1  # 1-5, with 1 being highest
    max_cost: Optional[float] = None
    prefer_cost_over_latency: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InferenceRequest':
        """Create an InferenceRequest from a dictionary."""
        # Convert compliance constraints to a set
        constraints = set(data.get('compliance_constraints', []))
        
        return cls(
            model_name=data.get('model_name', ''),
            input_token_size=data.get('input_token_size', 0),
            required_latency_ms=data.get('required_latency_ms', 0),
            compliance_constraints=constraints,
            unique_id=data.get('unique_id', f"req_{int(time.time())}"),
            priority=data.get('priority', 1),
            max_cost=data.get('max_cost'),
            prefer_cost_over_latency=data.get('prefer_cost_over_latency', False)
        )


@dataclass
class Backend:
    """
    Represents a hardware backend capable of running AI model inference.
    
    Attributes:
        backend_id: Unique identifier for the backend
        chip_type: Type of hardware chip (e.g., "GPU", "TPU", "Groq LPU", "Cerebras")
        latency_ms: Expected latency in milliseconds for standard inference
        cost_per_token: Cost per token in dollars
        region: Geographic region where the backend is located
        supported_models: List of model names supported by this backend
        status: Current operational status
        compliance_tags: Set of compliance features provided by this backend
        max_token_size: Maximum token size this backend can handle
        current_load: Current load percentage (0-100)
        estimated_queue_time_ms: Estimated time a new request would spend in queue
    """
    backend_id: str
    chip_type: str
    latency_ms: int
    cost_per_token: float
    region: str
    supported_models: List[str]
    status: BackendStatus
    compliance_tags: Set[str]
    max_token_size: int
    current_load: float = 0.0
    estimated_queue_time_ms: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Backend':
        """Create a Backend from a dictionary."""
        # Convert compliance tags to a set
        tags = set(data.get('compliance_tags', []))
        
        return cls(
            backend_id=data.get('backend_id', ''),
            chip_type=data.get('chip_type', ''),
            latency_ms=data.get('latency_ms', 0),
            cost_per_token=data.get('cost_per_token', 0.0),
            region=data.get('region', ''),
            supported_models=data.get('supported_models', []),
            status=BackendStatus.from_str(data.get('status', 'down')),
            compliance_tags=tags,
            max_token_size=data.get('max_token_size', 0),
            current_load=data.get('current_load', 0.0),
            estimated_queue_time_ms=data.get('estimated_queue_time_ms', 0)
        )


class FilterReason(TypedDict):
    """Represents a reason why a backend was filtered out."""
    backend: Backend
    reason: str


@dataclass
class RoutingResult:
    """
    Result of a routing decision, including the selected backend and related metadata.
    
    Attributes:
        request: The original inference request
        selected_backend: The chosen backend, if any
        score: Score of the selected backend (lower is better)
        considered_backends: List of backends that were considered
        filtered_out: List of backends that were filtered out with reasons
        is_fallback: Whether this is a fallback selection
        original_backend: The originally selected backend if this is a fallback
        fallback_reason: Reason for fallback if applicable
        final_latency_ms: Expected latency for the selected backend
        final_cost: Expected cost for the selected backend
        sla_met: Whether the required latency SLA was met
    """
    request: InferenceRequest
    selected_backend: Optional[Backend]
    score: float
    considered_backends: List[Backend]
    filtered_out: List[FilterReason]
    is_fallback: bool = False
    original_backend: Optional[Backend] = None
    fallback_reason: str = ""
    final_latency_ms: int = 0
    final_cost: float = 0.0
    sla_met: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the routing result to a dictionary for display/logging."""
        output = {
            "request_info": {
                "id": self.request.unique_id,
                "model": self.request.model_name,
                "input_tokens": self.request.input_token_size,
                "required_latency_ms": self.request.required_latency_ms,
                "compliance": list(self.request.compliance_constraints),
                "priority": self.request.priority,
                "max_cost": self.request.max_cost,
                "prefer_cost_over_latency": self.request.prefer_cost_over_latency
            },
            "considered_backends": [
                {
                    "id": backend.backend_id,
                    "chip": backend.chip_type,
                    "region": backend.region,
                    "status": str(backend.status)
                }
                for backend in self.considered_backends
            ],
            "filtered_backends": [
                {
                    "id": reason["backend"].backend_id,
                    "chip": reason["backend"].chip_type,
                    "region": reason["backend"].region,
                    "reason": reason["reason"]
                }
                for reason in self.filtered_out
            ],
            "is_fallback": self.is_fallback,
            "sla_met": self.sla_met
        }
        
        if self.selected_backend:
            output["decision"] = {
                "selected_backend_id": self.selected_backend.backend_id,
                "chip_type": self.selected_backend.chip_type,
                "region": self.selected_backend.region,
                "status": str(self.selected_backend.status),
                "score": self.score,
                "final_latency_ms": self.final_latency_ms,
                "final_cost": self.final_cost,
                "estimated_queue_time_ms": self.selected_backend.estimated_queue_time_ms,
                "current_load": self.selected_backend.current_load
            }
        else:
            output["decision"] = {
                "error": "No compatible backend found"
            }
        
        if self.is_fallback and self.original_backend:
            output["fallback_info"] = {
                "original_backend_id": self.original_backend.backend_id,
                "original_chip_type": self.original_backend.chip_type,
                "failure_reason": self.fallback_reason,
            }
        
        return output


class NetworkLatencyMap:
    """Manages network latency data between regions."""
    
    def __init__(self, latency_file: Optional[str] = None):
        """Initialize with an optional latency data file."""
        self.latency_map = {}
        if latency_file:
            self.load_latency_data(latency_file)
        else:
            # Initialize with some default values
            self._initialize_default_latencies()
    
    def _initialize_default_latencies(self):
        """Initialize with reasonable default latencies based on geographic proximity."""
        # Define some common regions
        regions = [
            "us-east-1", "us-west-1", "us-west-2", 
            "eu-west-1", "eu-central-1", 
            "ap-northeast-1", "ap-southeast-1", "global"
        ]
        
        # Create empty map structure
        for r1 in regions:
            self.latency_map[r1] = {}
            for r2 in regions:
                # Default high latency
                self.latency_map[r1][r2] = 150
        
        # Set reasonable values based on geography
        # Same region
        for r in regions:
            self.latency_map[r][r] = 1  # Nearly instant within same region
        
        # US east-west
        self.latency_map["us-east-1"]["us-west-1"] = 70
        self.latency_map["us-west-1"]["us-east-1"] = 70
        self.latency_map["us-east-1"]["us-west-2"] = 80
        self.latency_map["us-west-2"]["us-east-1"] = 80
        self.latency_map["us-west-1"]["us-west-2"] = 20
        self.latency_map["us-west-2"]["us-west-1"] = 20
        
        # US to EU
        self.latency_map["us-east-1"]["eu-west-1"] = 80
        self.latency_map["eu-west-1"]["us-east-1"] = 80
        self.latency_map["us-east-1"]["eu-central-1"] = 90
        self.latency_map["eu-central-1"]["us-east-1"] = 90
        self.latency_map["us-west-1"]["eu-west-1"] = 140
        self.latency_map["eu-west-1"]["us-west-1"] = 140
        
        # EU internal
        self.latency_map["eu-west-1"]["eu-central-1"] = 25
        self.latency_map["eu-central-1"]["eu-west-1"] = 25
        
        # Asia internal
        self.latency_map["ap-northeast-1"]["ap-southeast-1"] = 70
        self.latency_map["ap-southeast-1"]["ap-northeast-1"] = 70
        
        # US to Asia
        self.latency_map["us-west-1"]["ap-northeast-1"] = 110
        self.latency_map["ap-northeast-1"]["us-west-1"] = 110
        self.latency_map["us-west-1"]["ap-southeast-1"] = 180
        self.latency_map["ap-southeast-1"]["us-west-1"] = 180
        self.latency_map["us-east-1"]["ap-northeast-1"] = 170
        self.latency_map["ap-northeast-1"]["us-east-1"] = 170
        
        # EU to Asia
        self.latency_map["eu-central-1"]["ap-southeast-1"] = 160
        self.latency_map["ap-southeast-1"]["eu-central-1"] = 160
        
        # Global to everywhere
        for r in regions:
            if r != "global":
                self.latency_map["global"][r] = 100
                self.latency_map[r]["global"] = 100
    
    def load_latency_data(self, latency_file: str):
        """Load latency data from a JSON file."""
        try:
            with open(latency_file, 'r') as f:
                self.latency_map = json.load(f)
            logger.info(f"Loaded network latency data from {latency_file}")
        except Exception as e:
            logger.error(f"Failed to load latency data from {latency_file}: {e}")
            self._initialize_default_latencies()
    
    def get_latency(self, from_region: str, to_region: str) -> int:
        """Get the network latency between two regions in milliseconds."""
        # If regions match, return minimal latency
        if from_region == to_region:
            return 1
        
        # Check if we have data for these regions
        if from_region in self.latency_map and to_region in self.latency_map[from_region]:
            return self.latency_map[from_region][to_region]
        
        # Fall back to default high latency if regions unknown
        logger.warning(f"No latency data for {from_region} -> {to_region}, assuming high latency")
        return 150
    
    def update_latency(self, from_region: str, to_region: str, latency_ms: int):
        """Update the latency between two regions."""
        if from_region not in self.latency_map:
            self.latency_map[from_region] = {}
        
        self.latency_map[from_region][to_region] = latency_ms
        logger.debug(f"Updated latency: {from_region} -> {to_region} = {latency_ms}ms")


class BackendScorer:
    """Handles scoring logic for backends based on various factors."""
    
    @staticmethod
    def calculate_base_score(backend: Backend, request: InferenceRequest) -> float:
        """Calculate the base score for a backend."""
        # Base score is a product of latency and cost per token
        return backend.latency_ms * backend.cost_per_token
    
    @staticmethod
    def apply_health_adjustment(score: float, backend: Backend) -> float:
        """Adjust score based on backend health status."""
        if backend.status == BackendStatus.DOWN:
            return float('inf')
        elif backend.status == BackendStatus.DEGRADED:
            return score * 1.5
        else:  # HEALTHY
            return score
    
    @staticmethod
    def apply_priority_adjustment(score: float, request: InferenceRequest) -> float:
        """Adjust score based on request priority."""
        # Higher priority (lower number) gets better score
        priority_factor = 1.0 / request.priority
        return score * priority_factor
    
    @staticmethod
    def apply_cost_preference_adjustment(score: float, backend: Backend, request: InferenceRequest) -> float:
        """Adjust score based on cost preference."""
        if request.prefer_cost_over_latency:
            # If cost optimization is preferred, make score more sensitive to cost differences
            cost_factor = backend.cost_per_token * 1000  # Amplify cost influence
            return score * cost_factor
        return score
    
    @staticmethod
    def apply_load_adjustment(score: float, backend: Backend) -> float:
        """Adjust score based on backend load and queue times."""
        # Heavily penalize backends with high queue times
        if backend.estimated_queue_time_ms > 100:
            return score * (1 + (backend.estimated_queue_time_ms / 100))
        
        # Also consider current load (to balance traffic)
        load_factor = 1 + (backend.current_load / 100)
        return score * load_factor
    
    @classmethod
    def score_backend(cls, backend: Backend, request: InferenceRequest, 
                     network_latency: int = 0) -> Tuple[float, int, float]:
        """
        Score a backend based on all relevant factors.
        
        Returns:
            Tuple of (final_score, estimated_total_latency, estimated_total_cost)
        """
        # Calculate base score
        base_score = cls.calculate_base_score(backend, request)
        
        # Apply adjustments
        health_adjusted = cls.apply_health_adjustment(base_score, backend)
        priority_adjusted = cls.apply_priority_adjustment(health_adjusted, request)
        cost_adjusted = cls.apply_cost_preference_adjustment(priority_adjusted, backend, request)
        load_adjusted = cls.apply_load_adjustment(cost_adjusted, backend)
        
        # Calculate total expected latency
        total_latency = backend.latency_ms + network_latency
        if backend.status == BackendStatus.DEGRADED:
            total_latency = int(total_latency * 1.5)  # 50% slower when degraded
        
        # Add estimated queue time
        total_latency += backend.estimated_queue_time_ms
        
        # Calculate total cost
        total_cost = backend.cost_per_token * request.input_token_size
        
        return load_adjusted, total_latency, total_cost


class BackendFilter:
    """Handles filtering of backends based on compatibility criteria."""
    
    @staticmethod
    def filter_by_status(backend: Backend, request: InferenceRequest) -> Optional[str]:  # takes both parameters
        """Filter backends by operational status."""
        if backend.status == BackendStatus.DOWN:
            return "Backend is down"
        return None
    
    @staticmethod
    def filter_by_model(backend: Backend, request: InferenceRequest) -> Optional[str]:
        """Filter backends by model compatibility."""
        if request.model_name not in backend.supported_models:
            return f"Model {request.model_name} not supported"
        return None
    
    @staticmethod
    def filter_by_token_size(backend: Backend, request: InferenceRequest) -> Optional[str]:
        """Filter backends by token size constraints."""
        if request.input_token_size > backend.max_token_size:
            return "Token size exceeds backend limit"
        return None
    
    @staticmethod
    def filter_by_compliance(backend: Backend, request: InferenceRequest) -> Optional[str]:
        """Filter backends by compliance requirements."""
        if not request.compliance_constraints.issubset(backend.compliance_tags):
            missing = request.compliance_constraints - backend.compliance_tags
            return f"Missing compliance tags: {missing}"
        return None
    
    @staticmethod
    def filter_by_latency(backend: Backend, request: InferenceRequest, 
                         network_latency: int = 0) -> Optional[str]:
        """
        Filter backends by latency requirements including network latency.
        
        Args:
            backend: The backend to evaluate
            request: The inference request
            network_latency: Network latency in ms between user and backend
        """
        # Calculate total latency including network
        total_latency = backend.latency_ms + network_latency
        
        # Add estimated queue time
        total_latency += backend.estimated_queue_time_ms
        
        # For degraded backends, estimate worse performance
        if backend.status == BackendStatus.DEGRADED:
            total_latency = int(total_latency * 1.5)  # 50% slower
        
        # Check against requirement
        if total_latency > request.required_latency_ms:
            return f"Total latency ({total_latency}ms) exceeds required SLA ({request.required_latency_ms}ms)"
        
        return None
    
    @staticmethod
    def filter_by_cost(backend: Backend, request: InferenceRequest) -> Optional[str]:
        """Filter backends by cost constraints if specified."""
        if request.max_cost is not None:
            estimated_cost = backend.cost_per_token * request.input_token_size
            if estimated_cost > request.max_cost:
                return f"Estimated cost (${estimated_cost:.6f}) exceeds maximum (${request.max_cost:.6f})"
        return None
    
    @classmethod
    def apply_filters(cls, backend: Backend, request: InferenceRequest, 
                     network_latency: int = 0) -> Optional[str]:
        """
        Apply all filters and return reason for incompatibility if any.
        
        Args:
            backend: The backend to evaluate
            request: The inference request
            network_latency: Network latency between user and backend
        """
        filters = [
            cls.filter_by_status,
            cls.filter_by_model,
            cls.filter_by_token_size, 
            cls.filter_by_compliance,
            lambda b, r: cls.filter_by_latency(b, r, network_latency),
            cls.filter_by_cost
        ]
        
        for filter_func in filters:
            reason = filter_func(backend, request)
            if reason:
                return reason
        
        return None


class TesseractRouter:
    """The main routing class that selects the optimal backend for inference requests."""
    
    def __init__(self, backends_file: str = "models/backends.json", 
                latency_file: Optional[str] = None, 
                user_region: str = "us-east-1"):
        """
        Initialize the router with a list of available backends.
        
        Args:
            backends_file: Path to JSON file with backend definitions
            latency_file: Optional path to network latency data
            user_region: Default region for user requests
        """
        self.backends: List[Backend] = []
        self.network_latency = NetworkLatencyMap(latency_file)
        self.user_region = user_region
        self._last_scoring_result = None  # Store the most recent scoring result
        self.load_backends(backends_file)
        logger.info(f"Tesseract Router initialized with {len(self.backends)} backends")
    
    def load_backends(self, backends_file: str) -> None:
        """Load backend configurations from a JSON file."""
        try:
            with open(backends_file, 'r') as f:
                backends_data = json.load(f)
            
            self.backends = [Backend.from_dict(backend) for backend in backends_data]
            logger.info(f"Loaded {len(self.backends)} backends from {backends_file}")
        except Exception as e:
            logger.error(f"Failed to load backends from {backends_file}: {e}")
            # Initialize with empty list if file can't be loaded
            self.backends = []
    
    def set_user_region(self, region: str) -> None:
        """Set the current user's region for latency calculations."""
        self.user_region = region
        logger.info(f"User region set to {region}")
    
    def route_request(self, request: InferenceRequest, user_region: Optional[str] = None) -> RoutingResult:
        """
        Route an inference request to the best available backend based on
        compatibility, performance, cost, and compliance requirements.
        
        Args:
            request: The inference request to route
            user_region: Optional region of the user, for calculating network latency
        """
        # Use provided user region or default
        region = user_region if user_region else self.user_region
        logger.info(f"Routing request {request.unique_id} for model {request.model_name} from {region}")
        
        # Step 1: Filter backends by compatibility and compliance
        compatible_backends, filtered_out = self._filter_compatible_backends(request, region)
        
        if not compatible_backends:
            logger.warning(f"No compatible backends found for request {request.unique_id}")
            return RoutingResult(
                request=request,
                selected_backend=None,
                score=float('inf'),
                considered_backends=[],
                filtered_out=filtered_out,
                final_latency_ms=0,
                final_cost=0.0,
                sla_met=False
            )
        
        # Step 2: Score and rank the compatible backends
        scored_backends = self._score_backends(request, compatible_backends, region)
        
        # Step 3: Select the best backend
        best_backend, best_score, total_latency, total_cost = scored_backends[0]
        
        # Check if SLA is met (for reporting, though we already filtered by this)
        sla_met = total_latency <= request.required_latency_ms
        
        logger.info(f"Selected {best_backend.chip_type} in {best_backend.region} "
                    f"for request {request.unique_id} with score {best_score:.4f}, "
                    f"latency {total_latency}ms")
        
        return RoutingResult(
            request=request,
            selected_backend=best_backend,
            score=best_score,
            considered_backends=[backend for backend, _, _, _ in scored_backends],
            filtered_out=filtered_out,
            final_latency_ms=total_latency,
            final_cost=total_cost,
            sla_met=sla_met
        )
    
    def update_backend_status(self, backend_id: str, new_status: str) -> bool:
        """
        Update the status of a backend.
        Returns True if successful, False if backend not found.
        """
        for backend in self.backends:
            if backend.backend_id == backend_id:
                old_status = backend.status
                backend.status = BackendStatus.from_str(new_status)
                logger.info(f"Backend {backend_id} status changed from {old_status} to {backend.status}")
                return True
        
        logger.warning(f"Backend {backend_id} not found, cannot update status")
        return False
    
    def update_backend_load(self, backend_id: str, load: float, queue_time_ms: int) -> bool:
        """
        Update the load and queue time metrics for a backend.
        Returns True if successful, False if backend not found.
        """
        for backend in self.backends:
            if backend.backend_id == backend_id:
                backend.current_load = max(0.0, min(100.0, load))  # Ensure between 0-100%
                backend.estimated_queue_time_ms = max(0, queue_time_ms)
                logger.debug(f"Backend {backend_id} load updated to {load}%, queue {queue_time_ms}ms")
                return True
        
        logger.warning(f"Backend {backend_id} not found, cannot update load metrics")
        return False
    
    def update_network_latency(self, from_region: str, to_region: str, latency_ms: int) -> None:
        """Update network latency data between two regions."""
        self.network_latency.update_latency(from_region, to_region, latency_ms)
    
    def simulate_backend_degradation(self) -> List[Tuple[str, str, str]]:
        """
        Randomly degrade or recover some backends to simulate real-world conditions.
        Returns a list of (backend_id, old_status, new_status) for backends that changed.
        """
        import random
        
        changes = []
        for backend in self.backends:
            # 10% chance to change status
            if random.random() < 0.1:
                old_status = backend.status
                
                # Determine new status based on current status
                if old_status == BackendStatus.HEALTHY:
                    # 80% chance to degrade, 20% chance to go down
                    new_status = BackendStatus.DEGRADED if random.random() < 0.8 else BackendStatus.DOWN
                elif old_status == BackendStatus.DEGRADED:
                    # 50% chance to recover, 50% chance to go down
                    new_status = BackendStatus.HEALTHY if random.random() < 0.5 else BackendStatus.DOWN
                else:  # DOWN
                    # 70% chance to be degraded, 30% chance to be healthy
                    new_status = BackendStatus.DEGRADED if random.random() < 0.7 else BackendStatus.HEALTHY
                
                backend.status = new_status
                changes.append((backend.backend_id, str(old_status), str(new_status)))
                logger.info(f"Backend {backend.backend_id} status changed from {old_status} to {new_status}")
                
                # Also simulate load changes
                backend.current_load = random.uniform(10.0, 90.0)
                backend.estimated_queue_time_ms = int(backend.current_load * random.uniform(0.5, 2.0))
        
        return changes
    
    def get_backend_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current statistics for all backends in the system.
        
        Returns:
            Dictionary mapping backend_id to stats dictionary
        """
        stats = {}
        for backend in self.backends:
            stats[backend.backend_id] = {
                "chip_type": backend.chip_type,
                "region": backend.region,
                "status": str(backend.status),
                "supported_models": backend.supported_models,
                "current_load": backend.current_load,
                "queue_time_ms": backend.estimated_queue_time_ms,
                "latency_ms": backend.latency_ms,
                "cost_per_token": backend.cost_per_token,
                "compliance_tags": list(backend.compliance_tags)
            }
        return stats
    
    def get_region_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics grouped by region.
        
        Returns:
            Dictionary mapping region to stats dictionary
        """
        stats = {}
        
        # Initialize regions
        for backend in self.backends:
            if backend.region not in stats:
                stats[backend.region] = {
                    "backend_count": 0,
                    "healthy_backends": 0,
                    "degraded_backends": 0,
                    "down_backends": 0,
                    "avg_load": 0.0,
                    "chip_types": set(),
                    "supported_models": set(),
                    "compliance_tags": set()
                }
        
        # Collect stats
        for backend in self.backends:
            region_stats = stats[backend.region]
            region_stats["backend_count"] += 1
            
            if backend.status == BackendStatus.HEALTHY:
                region_stats["healthy_backends"] += 1
            elif backend.status == BackendStatus.DEGRADED:
                region_stats["degraded_backends"] += 1
            else:  # DOWN
                region_stats["down_backends"] += 1
            
            region_stats["avg_load"] += backend.current_load
            region_stats["chip_types"].add(backend.chip_type)
            region_stats["supported_models"].update(backend.supported_models)
            region_stats["compliance_tags"].update(backend.compliance_tags)
        
        # Calculate averages and convert sets to lists
        for region, region_stats in stats.items():
            if region_stats["backend_count"] > 0:
                region_stats["avg_load"] /= region_stats["backend_count"]
            
            region_stats["chip_types"] = list(region_stats["chip_types"])
            region_stats["supported_models"] = list(region_stats["supported_models"])
            region_stats["compliance_tags"] = list(region_stats["compliance_tags"])
        
        return stats
    
    def get_global_routing_stats(self) -> Dict[str, Any]:
        """
        Get global statistics about the routing system.
        
        Returns:
            Dictionary with global stats
        """
        total_backends = len(self.backends)
        healthy_backends = sum(1 for b in self.backends if b.status == BackendStatus.HEALTHY)
        degraded_backends = sum(1 for b in self.backends if b.status == BackendStatus.DEGRADED)
        down_backends = sum(1 for b in self.backends if b.status == BackendStatus.DOWN)
        
        # Get unique regions, chip types, and models
        regions = set(b.region for b in self.backends)
        chip_types = set(b.chip_type for b in self.backends)
        models = set()
        for backend in self.backends:
            models.update(backend.supported_models)
        
        # Get average load across all healthy backends
        avg_load = 0.0
        healthy_count = 0
        for backend in self.backends:
            if backend.status != BackendStatus.DOWN:
                avg_load += backend.current_load
                healthy_count += 1
        
        if healthy_count > 0:
            avg_load /= healthy_count
        
        return {
            "total_backends": total_backends,
            "healthy_backends": healthy_backends,
            "degraded_backends": degraded_backends,
            "down_backends": down_backends,
            "unique_regions": len(regions),
            "regions": list(regions),
            "unique_chip_types": len(chip_types),
            "chip_types": list(chip_types),
            "supported_models": list(models),
            "avg_system_load": avg_load,
            "healthy_percentage": (healthy_backends / total_backends * 100) if total_backends > 0 else 0
        }
    
    def get_routing_recommendations(self, model_name: str, required_latency_ms: int,
                                   compliance_constraints: List[str],
                                   from_region: str) -> Dict[str, Any]:
        """
        Get recommendations on backends for a specific request profile.
        
        Args:
            model_name: Model to use
            required_latency_ms: Required latency SLA
            compliance_constraints: List of compliance tags required
            from_region: Source region of request
            
        Returns:
            Dictionary with recommendations
        """
        # Create a test request
        request = InferenceRequest(
            model_name=model_name,
            input_token_size=1000,  # Example size
            required_latency_ms=required_latency_ms,
            compliance_constraints=set(compliance_constraints),
            priority=1
        )
        
        # Get a routing result
        result = self.route_request(request, from_region)
        
        # Build recommendations based on the result
        recommendations = {
            "can_route": result.selected_backend is not None,
            "sla_met": result.sla_met,
            "request_profile": {
                "model": model_name,
                "required_latency_ms": required_latency_ms,
                "compliance_constraints": compliance_constraints,
                "from_region": from_region
            }
        }
        
        if result.selected_backend:
            recommendations["recommended_backend"] = {
                "backend_id": result.selected_backend.backend_id,
                "chip_type": result.selected_backend.chip_type,
                "region": result.selected_backend.region,
                "estimated_latency_ms": result.final_latency_ms,
                "estimated_cost": result.final_cost
            }
            
            # Add alternative backends if any
            alternatives = []
            for backend in result.considered_backends[1:3]:  # Top 3 alternatives
                # Calculate latency and cost
                network_latency = self.network_latency.get_latency(from_region, backend.region)
                _, total_latency, total_cost = BackendScorer.score_backend(
                    backend, request, network_latency
                )
                
                alternatives.append({
                    "backend_id": backend.backend_id,
                    "chip_type": backend.chip_type,
                    "region": backend.region,
                    "estimated_latency_ms": total_latency,
                    "estimated_cost": total_cost,
                    "meets_sla": total_latency <= required_latency_ms
                })
            
            recommendations["alternatives"] = alternatives
        
        # Analyze why routing might have failed
        if not result.selected_backend:
            reasons = {}
            for filtered in result.filtered_out:
                reason = filtered["reason"]
                if reason in reasons:
                    reasons[reason] += 1
                else:
                    reasons[reason] = 1
            
            recommendations["routing_failure_analysis"] = {
                "filtered_backends_count": len(result.filtered_out),
                "common_reasons": reasons
            }
            
            # Suggest ways to fix the issue
            suggestions = []
            if "Model" in str(reasons):
                suggestions.append("Request a different supported model")
            if "latency" in str(reasons):
                suggestions.append("Increase latency SLA or request from a region closer to compatible backends")
            if "compliance" in str(reasons):
                suggestions.append("Adjust compliance requirements if possible")
            
            recommendations["suggestions"] = suggestions
        
        return recommendations
    
    def _filter_compatible_backends(self, request: InferenceRequest, 
                                  user_region: str) -> Tuple[List[Backend], List[FilterReason]]:
        """
        Filter backends based on compatibility with the request.
        Returns a tuple of (compatible_backends, filtered_out_backends_with_reasons)
        """
        compatible_backends = []
        filtered_out = []
        
        for backend in self.backends:
            # Calculate network latency between user and this backend
            network_latency = self.network_latency.get_latency(user_region, backend.region)
            
            # Apply all filters
            reason = BackendFilter.apply_filters(backend, request, network_latency)
            
            if reason:
                filtered_out.append({"backend": backend, "reason": reason})
            else:
                compatible_backends.append(backend)
        
        return compatible_backends, filtered_out
    
    def _score_backends(self, request: InferenceRequest, backends: List[Backend], 
                      user_region: str) -> List[Tuple[Backend, float, int, float]]:
        """
        Score each backend based on a weighted combination of factors.
        Return a list of (backend, score, total_latency, total_cost) tuples sorted by score (lower is better).
        """
        scored_backends = []
        
        for backend in backends:
            # Calculate network latency between user and this backend
            network_latency = self.network_latency.get_latency(user_region, backend.region)
            
            # Score the backend
            score, total_latency, total_cost = BackendScorer.score_backend(
                backend, request, network_latency
            )
            
            scored_backends.append((backend, score, total_latency, total_cost))
        
        # Sort by score (lower is better)
        result = sorted(scored_backends, key=lambda x: x[1])
        
        # Store this result for later access
        self._last_scoring_result = result
        
        return result
    
    def handle_backend_failure(self, routing_result: RoutingResult, 
                             failure_reason: str, 
                             user_region: Optional[str] = None) -> RoutingResult:
        """
        Handle a backend failure by rerouting to the next best backend.
        """
        if not routing_result.selected_backend:
            logger.error("Cannot handle failure: no backend was selected")
            return routing_result
        
        # Log the failure
        failed_backend = routing_result.selected_backend
        logger.warning(f"Backend {failed_backend.backend_id} ({failed_backend.chip_type}) failed: {failure_reason}")
        
        # Use provided user region or default
        region = user_region if user_region else self.user_region
        
        # Get all backends that were considered except the failed one
        remaining_backends = [b for b in routing_result.considered_backends 
                             if b.backend_id != failed_backend.backend_id]
        
        if not remaining_backends:
            logger.error(f"No fallback backends available for request {routing_result.request.unique_id}")
            
            # Add the failed backend to filtered_out list
            filtered_out = routing_result.filtered_out.copy()
            filtered_out.append({"backend": failed_backend, "reason": failure_reason})
            
            return RoutingResult(
                request=routing_result.request,
                selected_backend=None,
                score=float('inf'),
                considered_backends=routing_result.considered_backends,
                filtered_out=filtered_out,
                is_fallback=True,
                original_backend=failed_backend,
                fallback_reason=failure_reason,
                sla_met=False
            )
        
        # Score the remaining backends
        scored_backends = self._score_backends(routing_result.request, remaining_backends, region)
        
        # Select the next best backend
        next_best_backend, next_best_score, total_latency, total_cost = scored_backends[0]
        
        # Check if SLA is still met with fallback
        sla_met = total_latency <= routing_result.request.required_latency_ms
        
        logger.info(f"Rerouting request {routing_result.request.unique_id} to fallback backend: "
                    f"{next_best_backend.chip_type} in {next_best_backend.region}, "
                    f"latency {total_latency}ms")
        
        # Add the failed backend to filtered_out list
        filtered_out = routing_result.filtered_out.copy()
        filtered_out.append({"backend": failed_backend, "reason": failure_reason})
        
        return RoutingResult(
            request=routing_result.request,
            selected_backend=next_best_backend,
            score=next_best_score,
            considered_backends=remaining_backends,
            filtered_out=filtered_out,
            is_fallback=True,
            original_backend=failed_backend,
            fallback_reason=failure_reason,
            final_latency_ms=total_latency,
            final_cost=total_cost,
            sla_met=sla_met
        )

# Helper function to load a request from a JSON file
def load_request(request_file: str) -> InferenceRequest:
    """Load an inference request from a JSON file."""
    try:
        with open(request_file, 'r') as f:
            request_data = json.load(f)
        
        return InferenceRequest.from_dict(request_data)
    except Exception as e:
        logger.error(f"Failed to load request from {request_file}: {e}")
        raise


# Helper function to load multiple requests from a JSON file
def load_all_requests(requests_file: str = "models/inference_request.json") -> List[InferenceRequest]:
    """Load all inference requests from a JSON file."""
    try:
        with open(requests_file, 'r') as f:
            requests_data = json.load(f)
        
        return [InferenceRequest.from_dict(req) for req in requests_data]
    except Exception as e:
        logger.error(f"Failed to load requests from {requests_file}: {e}")
        return []

