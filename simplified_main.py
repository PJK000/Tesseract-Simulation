
#!/usr/bin/env python3
"""
Tesseract AI Inference Router - Main CLI Interface

This is the main entry point for the Tesseract Inference Router simulation.
It provides a CLI interface to demonstrate the routing capabilities described
in the Tesseract whitepaper, allowing users to test different scenarios and
visualize the results.

Tesseract is a chip-agnostic, latency-aware routing layer for real-time AI inference
that intelligently routes requests to the most appropriate hardware backend based on:
- Latency requirements (SLA)
- Compliance constraints
- Model compatibility
- Cost efficiency
- Geographic/compliance constraints
- Backend health

Usage:
    python main.py
    python main.py --dashboard  # Starts with the dashboard UI
    python main.py --fluctuate  # Enables backend fluctuation
    python main.py --region [REGION]  # Sets the user's region (e.g., us-east-1)
"""

import os
import sys
import json
import time
import random
import argparse
import logging
import threading

from typing import Dict, List, Optional, Set, Tuple, Any, Callable, TypedDict
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Tesseract")

# Import local modules
from tesseract_router import (
    TesseractRouter, 
    InferenceRequest, 
    Backend, 
    BackendStatus, 
    load_all_requests,
    NetworkLatencyMap
)


class ColorFormatter:
    """Provides ANSI color codes for terminal visualization."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    
    @classmethod
    def status_color(cls, status: str) -> str:
        """Get the appropriate color for a status."""
        if status == "healthy":
            return cls.GREEN
        elif status == "degraded":
            return cls.YELLOW
        else:  # down
            return cls.RED


class RoutingVisualizer:
    """Provides visualization functions for routing decisions."""
    
    @staticmethod
    def print_routing_decision(decision: Dict[str, Any]) -> None:
        """
        Print a visualization of a routing decision using terminal colors.
        
        Args:
            decision: A dictionary containing the routing decision
        """
        c = ColorFormatter
        
        # Print header
        print(f"\n{c.BOLD}{c.BLUE}===== TESSERACT ROUTING DECISION ====={c.RESET}\n")
        
        # Print request info
        req_info = decision["request_info"]
        print(f"{c.BOLD}{c.MAGENTA}Request Information:{c.RESET}")
        print(f"  Request ID: {req_info['id']}")
        print(f"  Model: {req_info['model']}")
        print(f"  Input Tokens: {req_info['input_tokens']}")
        print(f"  Required Latency: {req_info['required_latency_ms']} ms")
        
        compliance_text = ', '.join(req_info['compliance']) if req_info['compliance'] else 'None'
        print(f"  Compliance Constraints: {compliance_text}")
        print(f"  Priority: {req_info['priority']}")
        
        if 'max_cost' in req_info and req_info['max_cost']:
            print(f"  Maximum Cost: ${req_info['max_cost']}")
        
        if req_info.get('prefer_cost_over_latency'):
            print(f"  Preference: Optimize for cost over latency")
        
        # Print decision
        print(f"\n{c.BOLD}Routing Decision:{c.RESET}")
        if "error" in decision["decision"]:
            print(f"  {c.RED}{c.BOLD}Error: {decision['decision']['error']}{c.RESET}")
            print(f"  {c.YELLOW}SLA Met: No{c.RESET}")
        else:
            selected = decision["decision"]
            print(f"  Selected: {c.BOLD}{c.CYAN}{selected['chip_type']}{c.RESET} in {c.GREEN}{selected['region']}{c.RESET}")
            print(f"  Backend ID: {selected['selected_backend_id']}")
            
            status_color = c.GREEN if selected['status'] == "healthy" else (c.YELLOW if selected['status'] == "degraded" else c.RED)
            print(f"  Status: {status_color}{c.BOLD}{selected['status'].capitalize()}{c.RESET}")
            
            print(f"  Score: {selected['score']:.6f}")
            print(f"  Expected Latency: {c.BOLD}{selected['final_latency_ms']} ms{c.RESET}")
            
            if 'estimated_queue_time_ms' in selected and selected['estimated_queue_time_ms'] > 0:
                print(f"  Queue Time: {selected['estimated_queue_time_ms']} ms")
                
            if 'current_load' in selected:
                load = selected['current_load']
                load_color = c.GREEN if load < 70 else (c.YELLOW if load < 90 else c.RED)
                print(f"  Current Load: {load_color}{load:.1f}%{c.RESET}")
            
            print(f"  Total Cost: ${selected['final_cost']:.6f}")
            
            sla_met = decision.get("sla_met", True)
            sla_color = c.GREEN if sla_met else c.RED
            print(f"  {sla_color}SLA Met: {'Yes' if sla_met else 'No'}{c.RESET}")
            
            if decision["is_fallback"]:
                fallback = decision["fallback_info"]
                print(f"\n  {c.BOLD}{c.RED}FALLBACK ROUTE{c.RESET}")
                print(f"  Original: {c.BOLD}{fallback['original_chip_type']}{c.RESET}")
                print(f"  Reason: {fallback['failure_reason']}")
        
        # Print considered backends
        print(f"\n{c.BOLD}Considered Backends:{c.RESET}")
        if not decision["considered_backends"]:
            print("  None")
        else:
            for backend in decision["considered_backends"]:
                status_color = c.GREEN if backend['status'] == "healthy" else (c.YELLOW if backend['status'] == "degraded" else c.RED)
                print(f"  {backend['id']} - {backend['chip']} in {backend['region']} - {status_color}{backend['status'].capitalize()}{c.RESET}")
        
        # Print filtered backends
        print(f"\n{c.BOLD}Filtered Out Backends:{c.RESET}")
        if not decision["filtered_backends"]:
            print("  None")
        else:
            for backend in decision["filtered_backends"]:
                print(f"  {backend['id']} - {backend['chip']} in {backend['region']}")
                print(f"    Reason: {backend['reason']}")
        
        print("\n")
    
    @staticmethod
    def visualize_routing_path(result: Dict[str, Any], user_region: str) -> None:
        """
        Visualize the routing path for a request using ASCII art.
        
        Args:
            result: The routing result dictionary
            user_region: The region of the user
        """
        c = ColorFormatter
        request = result["request_info"]
        
        print(f"\n{c.BOLD}{c.CYAN}Routing Path:{c.RESET}\n")
        
        # Step 1: User
        print(f"  {c.BOLD}User{c.RESET} ({user_region})")
        print("     │")
        print("     ▼")
        
        # Step 2: Edge Gateway (conceptual in the simulation)
        print(f"  {c.BOLD}Tesseract Edge Gateway{c.RESET}")
        print("     │")
        print("     ▼")
        
        # Step 3: Global Router
        print(f"  {c.BOLD}Tesseract Global Router{c.RESET}")
        print(f"  {c.GRAY}└─ Latency map, resource map, policy map{c.RESET}")
        print("     │")
        print("     ▼")
        
        # Step 4: Backend Selection
        if "error" in result["decision"]:
            print(f"  {c.RED}{c.BOLD}Error: No Compatible Backend{c.RESET}")
        else:
            selected = result["decision"]
            
            if result["is_fallback"]:
                fallback = result["fallback_info"]
                
                # Original backend that failed
                print(f"  {c.BOLD}Primary Backend{c.RESET}: {fallback['original_chip_type']}")
                print(f"  {c.RED}Failed: {fallback['failure_reason']}{c.RESET}")
                print("     │")
                print("     ▼")
                
                # Fallback backend
                print(f"  {c.YELLOW}{c.BOLD}Fallback Backend{c.RESET}: {selected['chip_type']} in {selected['region']}")
                
                # Add estimated latency
                if 'final_latency_ms' in selected:
                    total_latency = selected['final_latency_ms']
                    sla_met = result.get("sla_met", True)
                    latency_color = c.GREEN if sla_met else c.RED
                    print(f"  {c.GRAY}└─ Est. Latency: {latency_color}{total_latency} ms{c.RESET}")
            else:
                print(f"  {c.GREEN}{c.BOLD}Selected Backend{c.RESET}: {selected['chip_type']} in {selected['region']}")
                
                # Add estimated latency
                if 'final_latency_ms' in selected:
                    total_latency = selected['final_latency_ms']
                    sla_met = result.get("sla_met", True)
                    latency_color = c.GREEN if sla_met else c.RED
                    print(f"  {c.GRAY}└─ Est. Latency: {latency_color}{total_latency} ms{c.RESET}")
        
        print()
    
    @staticmethod
    def create_health_heatmap(backends: List[Dict[str, Any]]) -> None:
        """
        Create a simple ASCII cluster health heatmap visualization.
        
        Args:
            backends: A list of backend dictionaries
        """
        c = ColorFormatter
        
        # Group backends by region and chip type
        regions = sorted(set(b["region"] for b in backends))
        chip_types = sorted(set(b["chip_type"] for b in backends))
        
        # Print header
        print(f"\n{c.BOLD}{c.CYAN}Tesseract Cluster Health Heatmap{c.RESET}\n")
        
        # Calculate column widths
        region_width = max(len(region) for region in regions) + 2
        chip_widths = {}
        for chip in chip_types:
            chip_widths[chip] = max(len(chip) + 2, 10)
        
        # Print header row
        print(" " * region_width, end="")
        for chip in chip_types:
            print(f"{c.BOLD}{chip.center(chip_widths[chip])}{c.RESET}", end="")
        print()
        
        # Print separator
        print("-" * (region_width + sum(chip_widths.values())))
        
        # Print rows
        for region in regions:
            print(f"{c.BOLD}{region.ljust(region_width)}{c.RESET}", end="")
            
            for chip in chip_types:
                # Find matching backends
                matching = [b for b in backends if b["region"] == region and b["chip_type"] == chip]
                
                if matching:
                    # Use the status of the first matching backend
                    backend = matching[0]
                    status = backend["status"]
                    
                    if status == "healthy":
                        status_text = f"{c.GREEN}■ Healthy{c.RESET}"
                    elif status == "degraded":
                        status_text = f"{c.YELLOW}■ Degraded{c.RESET}"
                    else:  # down
                        status_text = f"{c.RED}■ Down{c.RESET}"
                    
                    print(status_text.center(chip_widths[chip]), end="")
                else:
                    print("-".center(chip_widths[chip]), end="")
            
            print()
        
        print()
    
    @staticmethod
    def display_latency_map(latency_map: Dict[str, Dict[str, int]], 
                          user_region: Optional[str] = None) -> None:
        """
        Display the network latency map between regions.
        
        Args:
            latency_map: The latency map (from_region -> to_region -> ms)
            user_region: Optional highlight for user's region
        """
        c = ColorFormatter
        
        print(f"\n{c.BOLD}{c.CYAN}Tesseract Network Latency Map (ms){c.RESET}\n")
        
        # Get all regions
        all_regions = set()
        for from_region, to_regions in latency_map.items():
            all_regions.add(from_region)
            all_regions.update(to_regions.keys())
        
        regions = sorted(all_regions)
        
        # Calculate column width
        region_width = max(len(region) for region in regions) + 2
        
        # Print header row
        print(" " * region_width, end="")
        for region in regions:
            region_display = region
            if user_region and region == user_region:
                region_display = f"{c.BOLD}{c.GREEN}{region}{c.RESET}"
            print(f"{region_display.center(region_width)}", end="")
        print()
        
        # Print separator
        print("-" * (region_width + region_width * len(regions)))
        
        # Print rows
        for from_region in regions:
            # Print row label
            row_label = from_region
            if user_region and from_region == user_region:
                row_label = f"{c.BOLD}{c.GREEN}{from_region}{c.RESET}"
            print(f"{row_label.ljust(region_width)}", end="")
            
            # Print latencies
            for to_region in regions:
                # Get latency
                latency = None
                if from_region in latency_map and to_region in latency_map[from_region]:
                    latency = latency_map[from_region][to_region]
                
                # Format latency
                if latency is None:
                    cell = "-"
                elif latency <= 20:
                    cell = f"{c.GREEN}{latency}{c.RESET}"
                elif latency <= 80:
                    cell = f"{c.YELLOW}{latency}{c.RESET}"
                else:
                    cell = f"{c.RED}{latency}{c.RESET}"
                
                # Highlight user's connections
                if user_region and (from_region == user_region or to_region == user_region):
                    cell = f"{c.BOLD}{cell}{c.RESET}"
                
                print(cell.center(region_width), end="")
            
            print()
        
        print()
        print(f"{c.GRAY}Note: Values represent network latency in milliseconds.{c.RESET}")
        print(f"{c.GREEN}Green{c.RESET}: <20ms, {c.YELLOW}Yellow{c.RESET}: 20-80ms, {c.RED}Red{c.RESET}: >80ms")
        print()
    
    @staticmethod
    def display_global_stats(stats: Dict[str, Any]) -> None:
        """Display global routing system statistics."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}{c.CYAN}Tesseract Global System Statistics{c.RESET}\n")
        
        # Backend stats
        print(f"{c.BOLD}Backend Statistics:{c.RESET}")
        print(f"  Total Backends: {stats['total_backends']}")
        
        healthy_pct = stats['healthy_percentage']
        health_color = c.GREEN if healthy_pct >= 80 else (c.YELLOW if healthy_pct >= 50 else c.RED)
        print(f"  Healthy Backends: {stats['healthy_backends']} ({health_color}{healthy_pct:.1f}%{c.RESET})")
        print(f"  Degraded Backends: {stats['degraded_backends']}")
        print(f"  Down Backends: {stats['down_backends']}")
        
        # System load
        load = stats['avg_system_load']
        load_color = c.GREEN if load < 70 else (c.YELLOW if load < 90 else c.RED)
        print(f"  Average System Load: {load_color}{load:.1f}%{c.RESET}")
        
        # Coverage
        print(f"\n{c.BOLD}Geographic Coverage:{c.RESET}")
        print(f"  Regions: {', '.join(stats['regions'])}")
        
        # Hardware diversity
        print(f"\n{c.BOLD}Hardware Diversity:{c.RESET}")
        print(f"  Chip Types: {', '.join(stats['chip_types'])}")
        # Hardware diversity
        print(f"\n{c.BOLD}Hardware Diversity:{c.RESET}")
        print(f"  Chip Types: {', '.join(stats['chip_types'])}")
        
        # Model support
        print(f"\n{c.BOLD}Model Support:{c.RESET}")
        print(f"  Supported Models: {', '.join(stats['supported_models'])}")
        
        print()

    @staticmethod
    def display_region_stats(region_stats: Dict[str, Dict[str, Any]], 
                           highlight_region: Optional[str] = None) -> None:
        """Display statistics for each region."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}{c.CYAN}Tesseract Region Statistics{c.RESET}\n")
        
        # Table header
        print(f"{c.BOLD}{'Region'.ljust(15)} | {'Backends'.center(10)} | {'Health'.center(15)} | " +
              f"{'Load'.center(10)} | {'Chip Types'.center(25)} | {'Compliance'.center(20)}{c.RESET}")
        print("-" * 100)
        
        # Table rows
        for region, stats in region_stats.items():
            # Highlight user's region
            region_display = region
            if highlight_region and region == highlight_region:
                region_display = f"{c.GREEN}{region}{c.RESET}"
            
            # Calculate health percentage
            total = stats['backend_count']
            healthy = stats['healthy_backends']
            health_pct = (healthy / total * 100) if total > 0 else 0
            health_color = c.GREEN if health_pct >= 80 else (c.YELLOW if health_pct >= 50 else c.RED)
            health_display = f"{health_color}{healthy}/{total} ({health_pct:.0f}%){c.RESET}"
            
            # Format load
            load = stats['avg_load']
            load_color = c.GREEN if load < 70 else (c.YELLOW if load < 90 else c.RED)
            load_display = f"{load_color}{load:.1f}%{c.RESET}"
            
            # Format chip types and compliance tags
            chip_types = ", ".join(stats['chip_types'][:2])
            if len(stats['chip_types']) > 2:
                chip_types += f"... (+{len(stats['chip_types']) - 2})"
            
            compliance = ", ".join(stats['compliance_tags'][:2])
            if len(stats['compliance_tags']) > 2:
                compliance += f"... (+{len(stats['compliance_tags']) - 2})"
            
            print(f"{region_display.ljust(15)} | {str(total).center(10)} | {health_display.center(15)} | " +
                  f"{load_display.center(10)} | {chip_types.center(25)} | {compliance.center(20)}")
        
        print()


class RouteSimulator:
    """Handles simulation of routing requests and failures."""
    
    @staticmethod
    def simulate_backend_failure(router: TesseractRouter, routing_result, 
                               failure_probability: float = 0.3,
                               user_region: Optional[str] = None) -> Any:
        """
        Simulate a random backend failure with a given probability.
        
        Args:
            router: The router instance
            routing_result: The routing result to potentially fail
            failure_probability: Probability of failure (0.0 to 1.0)
            user_region: Optional user region for the fallback routing
            
        Returns:
            The original or rerouted result
        """
        if random.random() < failure_probability and routing_result.selected_backend:
            # Generate a random failure reason
            failure_reasons = [
                "Backend connection timeout",
                "Model not supported for the given input shape",
                "Backend capacity exceeded",
                "Rate limit reached",
                "Internal backend error",
                "Token size too large",
                "Inference failed with status code 500",
                "Hardware acceleration failure",
                "Memory allocation error",
                "KV cache corruption"
            ]
            failure_reason = random.choice(failure_reasons)
            
            # Handle the failure
            return router.handle_backend_failure(routing_result, failure_reason, user_region)
        
        return routing_result


class TesseractInitializer:
    """Handles initialization of the Tesseract environment and configuration."""
    
    @staticmethod
    def create_required_directories():
        """Create required directories if they don't exist."""
        os.makedirs("models", exist_ok=True)
        os.makedirs("configs", exist_ok=True)
    
    @staticmethod
    def create_default_backends_file():
        """Create a default backends.json file if it doesn't exist."""
        if not os.path.exists("models/backends.json"):
            logger.info("Creating default backends.json file...")
            
            default_backends = [          
  {
    "backend_id": "nvidia-h100-us-east",
    "chip_type": "NVIDIA H100",
    "latency_ms": 80,
    "cost_per_token": 0.000025,
    "region": "us-east-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-opus", "gemini-pro"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "gdpr", "sox", "us-data-residency"],
    "max_token_size": 32000,
    "current_load": 65.0,
    "estimated_queue_time_ms": 25
  },
  {
    "backend_id": "nvidia-a100-us-west",
    "chip_type": "NVIDIA A100",
    "latency_ms": 95,
    "cost_per_token": 0.000018,
    "region": "us-west-2",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-sonnet", "gemini-pro"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 24000,
    "current_load": 78.0,
    "estimated_queue_time_ms": 45
  },
  {
    "backend_id": "tpu-v5p-us-central",
    "chip_type": "Google TPU v5p",
    "latency_ms": 65,
    "cost_per_token": 0.000022,
    "region": "us-central1",
    "supported_models": ["gemini-pro", "gemini-flash", "llama-3-70b", "claude-3-sonnet"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "us-data-residency"],
    "max_token_size": 16000,
    "current_load": 55.0,
    "estimated_queue_time_ms": 15
  },
  {
    "backend_id": "groq-lpu-us-east",
    "chip_type": "Groq LPU",
    "latency_ms": 25,
    "cost_per_token": 0.000032,
    "region": "us-east-1",
    "supported_models": ["llama-3-70b", "llama-3-8b", "gemma-7b"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 12000,
    "current_load": 40.0,
    "estimated_queue_time_ms": 5
  },
  {
    "backend_id": "cerebras-us-west",
    "chip_type": "Cerebras CS-2",
    "latency_ms": 45,
    "cost_per_token": 0.000028,
    "region": "us-west-1",
    "supported_models": ["claude-3-opus", "claude-3-sonnet", "cerebras-lm"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 20000,
    "current_load": 30.0,
    "estimated_queue_time_ms": 10
  },
  {
    "backend_id": "nvidia-h100-eu-west",
    "chip_type": "NVIDIA H100",
    "latency_ms": 85,
    "cost_per_token": 0.000028,
    "region": "eu-west-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-opus", "mistral-large"],
    "status": "healthy",
    "compliance_tags": ["gdpr", "eu-data-residency"],
    "max_token_size": 32000,
    "current_load": 72.0,
    "estimated_queue_time_ms": 35
  },
  {
    "backend_id": "nvidia-a100-eu-central",
    "chip_type": "NVIDIA A100",
    "latency_ms": 100,
    "cost_per_token": 0.000020,
    "region": "eu-central-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-sonnet", "mistral-large"],
    "status": "healthy",
    "compliance_tags": ["gdpr", "eu-data-residency"],
    "max_token_size": 24000,
    "current_load": 60.0,
    "estimated_queue_time_ms": 25
  },
  {
    "backend_id": "tpu-v5p-eu-west",
    "chip_type": "Google TPU v5p",
    "latency_ms": 70,
    "cost_per_token": 0.000024,
    "region": "eu-west-1",
    "supported_models": ["gemini-pro", "gemini-flash", "llama-3-70b"],
    "status": "healthy",
    "compliance_tags": ["gdpr", "eu-data-residency"],
    "max_token_size": 16000,
    "current_load": 45.0,
    "estimated_queue_time_ms": 12
  },
  {
    "backend_id": "nvidia-h100-ap-northeast",
    "chip_type": "NVIDIA H100",
    "latency_ms": 90,
    "cost_per_token": 0.000030,
    "region": "ap-northeast-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-opus"],
    "status": "healthy",
    "compliance_tags": ["apac-compliance"],
    "max_token_size": 32000,
    "current_load": 55.0,
    "estimated_queue_time_ms": 20
  },
  {
    "backend_id": "nvidia-a100-ap-southeast",
    "chip_type": "NVIDIA A100",
    "latency_ms": 105,
    "cost_per_token": 0.000022,
    "region": "ap-southeast-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-sonnet"],
    "status": "healthy",
    "compliance_tags": ["apac-compliance"],
    "max_token_size": 24000,
    "current_load": 70.0,
    "estimated_queue_time_ms": 30
  },
  {
    "backend_id": "inferentia-2-us-east",
    "chip_type": "AWS Inferentia 2",
    "latency_ms": 125,
    "cost_per_token": 0.000012,
    "region": "us-east-1",
    "supported_models": ["llama-3-8b", "gemma-7b", "mistral-medium"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 8000,
    "current_load": 25.0,
    "estimated_queue_time_ms": 5
  },
  {
    "backend_id": "azure-maia-us-east",
    "chip_type": "Azure Maia 100",
    "latency_ms": 75,
    "cost_per_token": 0.000026,
    "region": "us-east-1",
    "supported_models": ["gpt-4", "llama-3-70b", "claude-3-opus", "azure-models"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "gdpr", "sox", "us-data-residency", "fedramp"],
    "max_token_size": 30000,
    "current_load": 45.0,
    "estimated_queue_time_ms": 15
  },
  {
    "backend_id": "cerebras-eu-central",
    "chip_type": "Cerebras CS-2",
    "latency_ms": 55,
    "cost_per_token": 0.000029,
    "region": "eu-central-1",
    "supported_models": ["claude-3-opus", "claude-3-sonnet", "cerebras-lm"],
    "status": "degraded",
    "compliance_tags": ["gdpr", "eu-data-residency"],
    "max_token_size": 20000,
    "current_load": 80.0,
    "estimated_queue_time_ms": 120
  },
  {
    "backend_id": "sambanova-us-west",
    "chip_type": "SambaNova",
    "latency_ms": 60,
    "cost_per_token": 0.000027,
    "region": "us-west-2",
    "supported_models": ["gpt-4", "llama-3-70b", "sambanova-models"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 22000,
    "current_load": 50.0,
    "estimated_queue_time_ms": 18
  },
  {
    "backend_id": "gaudi2-us-east",
    "chip_type": "Intel Gaudi 2",
    "latency_ms": 110,
    "cost_per_token": 0.000015,
    "region": "us-east-1",
    "supported_models": ["llama-3-8b", "gemma-7b", "mistral-medium", "intel-lm"],
    "status": "healthy",
    "compliance_tags": ["hipaa", "sox", "us-data-residency"],
    "max_token_size": 10000,
    "current_load": 35.0,
    "estimated_queue_time_ms": 8
  }
]
            
            with open("models/backends.json", 'w') as f:
                json.dump(default_backends, f, indent=2)
    
    @staticmethod
    def create_default_requests_file():
        """Create a default inference_request.json file if it doesn't exist."""
        if not os.path.exists("models/inference_request.json"):
            logger.info("Creating default inference_request.json file...")
            
            default_requests = [
                # High-priority, low-latency request with EU compliance
                {
                    "unique_id": "req_001",
                    "model_name": "llama-3-70b",
                    "input_token_size": 1024,
                    "required_latency_ms": 200,
                    "compliance_constraints": ["eu-data-residency"],
                    "priority": 1
                },
                
                # Health care request with HIPAA compliance
                {
                    "unique_id": "req_002",
                    "model_name": "gpt-4",
                    "input_token_size": 4096,
                    "required_latency_ms": 500,
                    "compliance_constraints": ["hipaa", "gdpr"],
                    "priority": 2,
                    "max_cost": 0.5
                },
                
                # Large context request with multiple compliance tags
                {
                    "unique_id": "req_003",
                    "model_name": "claude-3-opus",
                    "input_token_size": 8192,
                    "required_latency_ms": 1000,
                    "compliance_constraints": ["sox-compliance", "gdpr"],
                    "priority": 3,
                    "prefer_cost_over_latency": True
                },
                
                # Ultra-low latency request (for real-time applications)
                {
                    "unique_id": "req_004",
                    "model_name": "mistral-8x7b",
                    "input_token_size": 2048,
                    "required_latency_ms": 100,
                    "compliance_constraints": [],
                    "priority": 1
                },
                
                # US-specific request
                {
                    "unique_id": "req_005",
                    "model_name": "llama-3-70b",
                    "input_token_size": 512,
                    "required_latency_ms": 150,
                    "compliance_constraints": ["us-data-residency"],
                    "priority": 1
                }
            ]
            
            with open("models/inference_request.json", 'w') as f:
                json.dump(default_requests, f, indent=2)
    
    @staticmethod
    def create_default_latency_map():
        """Create a default network latency map file if it doesn't exist."""
        if not os.path.exists("configs/latency_map.json"):
            logger.info("Creating default latency_map.json file...")
            
            # Initialize a NetworkLatencyMap to get default values
            latency_map = NetworkLatencyMap()
            
            with open("configs/latency_map.json", 'w') as f:
                json.dump(latency_map.latency_map, f, indent=2)
    
    @classmethod
    def setup_environment(cls):
        """Set up the Tesseract environment."""
        logger.info("Setting up Tesseract environment...")
        cls.create_required_directories()
        cls.create_default_backends_file()
        cls.create_default_requests_file()
        cls.create_default_latency_map()


class TesseractCLI:
    """Command-line interface for the Tesseract router."""
    
    def __init__(self, router: TesseractRouter, requests: List[InferenceRequest], args):
        """Initialize the CLI with a router and request list."""
        self.router = router
        self.requests = requests
        self.args = args
        self.routing_results = []  # Store recent routing results for reporting
        self.user_region = args.region
    
    def display_menu(self):
        """Display the main menu options."""
        c = ColorFormatter
        print(f"\n{c.BOLD}Available Actions:{c.RESET}")
        print("1. Route a single request")
        print("2. Route multiple requests")
        print("3. View cluster health heatmap")
        print("4. View network latency map")
        print("5. View system statistics")
        print("6. Toggle backend status")
        print("7. Simulate backend fluctuation")
        print("8. Modify request parameters")
        print("9. Get routing recommendations")
        print("10. Change user region")
        print("11. Exit")
    
    def get_user_choice(self, prompt: str, default: int = 1, max_value: int = None) -> int:
        """Get a numeric choice from the user with validation."""
        try:
            value = int(input(prompt) or str(default))
            if max_value and (value < 1 or value > max_value):
                print(f"{ColorFormatter.RED}Invalid choice. Using default: {default}{ColorFormatter.RESET}")
                return default
            return value
        except ValueError:
            print(f"{ColorFormatter.RED}Invalid input. Using default: {default}{ColorFormatter.RESET}")
            return default
    
    def get_yes_no_input(self, prompt: str, default: bool = False) -> bool:
        """Get a yes/no response from the user."""
        try:
            response = input(prompt).lower()
            if not response:
                return default
            return response.startswith('y')
        except:
            return default
    
    def route_single_request(self):
        """Handle routing a single request."""
        c = ColorFormatter
        
        # Display available requests
        print(f"\n{c.BOLD}Available Requests:{c.RESET}")
        for i, req in enumerate(self.requests):
            compliance_str = ', '.join(req.compliance_constraints) if req.compliance_constraints else "None"
            print(f"{i+1}. {req.model_name} ({req.input_token_size} tokens, {req.required_latency_ms}ms SLA, Compliance: {compliance_str})")
        
        # Get request selection
        req_idx = self.get_user_choice(
            f"Select a request (1-{len(self.requests)}): ", 
            default=1, 
            max_value=len(self.requests)
        ) - 1
        
        request = self.requests[req_idx]
        
        # Route the request
        result = self.router.route_request(request, self.user_region)
        
        # Check if we should simulate failure
        simulate_fail = self.get_yes_no_input("Simulate a potential backend failure? (y/n): ")
        
        if simulate_fail:
            result = RouteSimulator.simulate_backend_failure(
                self.router, result, failure_probability=1.0, user_region=self.user_region
            )
        
        # Store result for statistics
        self.routing_results.append(result)
        
        # Format and print the decision
        formatted_result = result.to_dict()
        RoutingVisualizer.print_routing_decision(formatted_result)
        RoutingVisualizer.visualize_routing_path(formatted_result, self.user_region)
    
    def route_multiple_requests(self):
        """Handle routing multiple requests."""
        c = ColorFormatter
        
        num_requests = self.get_user_choice("How many random requests to route? ", default=5)
        simulate_failures = self.get_yes_no_input("Simulate random failures? (y/n): ", default=True)
        
        # Ask for specific compliance constraints
        use_compliance = self.get_yes_no_input("Apply specific compliance constraints? (y/n): ", default=False)
        compliance_constraints = set()
        if use_compliance:
            print(f"\n{c.BOLD}Available compliance options:{c.RESET}")
            print("1. GDPR (EU data protection)")
            print("2. HIPAA (US healthcare)")
            print("3. SOX (financial)")
            print("4. EU data residency")
            print("5. US data residency")
            
            choice = self.get_user_choice("Select option (1-5): ", default=1, max_value=5)
            if choice == 1:
                compliance_constraints.add("gdpr")
            elif choice == 2:
                compliance_constraints.add("hipaa")
            elif choice == 3:
                compliance_constraints.add("sox-compliance")
            elif choice == 4:
                compliance_constraints.add("eu-data-residency")
            elif choice == 5:
                compliance_constraints.add("us-data-residency")
        
        # Ask for specific latency SLA
        use_custom_sla = self.get_yes_no_input("Specify custom latency SLA? (y/n): ", default=False)
        latency_sla = None
        if use_custom_sla:
            try:
                latency_sla = int(input("Enter required latency in ms (20-1000): ") or "200")
                latency_sla = max(50, min(1000, latency_sla))
            except ValueError:
                latency_sla = 200
                print(f"{c.YELLOW}Invalid input. Using default: 200ms{c.RESET}")
        
        # Display progress bar
        print("\nRouting requests:")
        print("[", end="")
        
        successful_routes = 0
        failed_routes = 0
        fallback_routes = 0
        
        for i in range(num_requests):
            # Select a random request
            request = random.choice(self.requests)
            
            # Apply custom constraints if specified
            if use_compliance and compliance_constraints:
                # Create a modified request with the specified compliance
                request = InferenceRequest(
                    model_name=request.model_name,
                    input_token_size=request.input_token_size,
                    required_latency_ms=latency_sla if latency_sla else request.required_latency_ms,
                    compliance_constraints=compliance_constraints,
                    priority=request.priority,
                    max_cost=request.max_cost,
                    prefer_cost_over_latency=request.prefer_cost_over_latency
                )
            elif latency_sla:
                # Just modify the latency SLA
                request = InferenceRequest(
                    model_name=request.model_name,
                    input_token_size=request.input_token_size,
                    required_latency_ms=latency_sla,
                    compliance_constraints=request.compliance_constraints,
                    priority=request.priority,
                    max_cost=request.max_cost,
                    prefer_cost_over_latency=request.prefer_cost_over_latency
                )
            
            # Route the request
            result = self.router.route_request(request, self.user_region)
            
            if simulate_failures:
                result = RouteSimulator.simulate_backend_failure(
                    self.router, result, failure_probability=0.3, user_region=self.user_region
                )
            
            # Store result for statistics
            self.routing_results.append(result)
            
            # Track statistics
            if result.selected_backend is None:
                failed_routes += 1
                print(f"{c.RED}✗{c.RESET}", end="", flush=True)
            elif result.is_fallback:
                fallback_routes += 1
                print(f"{c.YELLOW}!{c.RESET}", end="", flush=True)
            else:
                successful_routes += 1
                print(f"{c.GREEN}✓{c.RESET}", end="", flush=True)
            
            # Small delay between requests
            time.sleep(0.2)
        
        print("]")
        
        # Print summary
        print(f"\n{c.BOLD}Routing Summary:{c.RESET}")
        print(f"  Total Requests: {num_requests}")
        print(f"  {c.GREEN}Successful Routes: {successful_routes}{c.RESET}")
        print(f"  {c.YELLOW}Fallback Routes: {fallback_routes}{c.RESET}")
        print(f"  {c.RED}Failed Routes: {failed_routes}{c.RESET}")
        
        success_rate = ((successful_routes + fallback_routes) / num_requests * 100) if num_requests > 0 else 0
        print(f"  Overall Success Rate: {success_rate:.1f}%")
        
        # Option to see detailed results
        if self.get_yes_no_input("\nShow detailed results? (y/n): ", default=False):
            for i, result in enumerate(self.routing_results[-num_requests:]):
                print(f"\n{c.BOLD}Request {i+1}:{c.RESET}")
                formatted_result = result.to_dict()
                RoutingVisualizer.print_routing_decision(formatted_result)
    
    def view_cluster_health(self):
        """Display the health heatmap of all backends."""
        backends_data = []
        for backend in self.router.backends:
            backends_data.append({
                "region": backend.region,
                "chip_type": backend.chip_type,
                "backend_id": backend.backend_id,
                "status": str(backend.status),
                "current_load": backend.current_load
            })
        
        RoutingVisualizer.create_health_heatmap(backends_data)
    
    def view_latency_map(self):
        """Display the network latency map."""
        RoutingVisualizer.display_latency_map(
            self.router.network_latency.latency_map, 
            self.user_region
        )
    
    def view_system_statistics(self):
        """Display system-wide statistics."""
        # Get global stats
        global_stats = self.router.get_global_routing_stats()
        RoutingVisualizer.display_global_stats(global_stats)
        
        # Get region stats
        region_stats = self.router.get_region_stats()
        RoutingVisualizer.display_region_stats(region_stats, self.user_region)
    
    def toggle_backend_status(self):
        """Allow the user to change the status of a backend."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}Available Backends:{c.RESET}")
        for i, backend in enumerate(self.router.backends):
            status_color = c.GREEN if backend.status == BackendStatus.HEALTHY else (
                c.YELLOW if backend.status == BackendStatus.DEGRADED else c.RED
            )
            print(f"{i+1}. {backend.chip_type} in {backend.region} - " + 
                  f"{status_color}{backend.status}{c.RESET} - " +
                  f"Load: {backend.current_load:.1f}%")
        
        backend_idx = self.get_user_choice(
            f"Select a backend (1-{len(self.router.backends)}): ", 
            default=1, 
            max_value=len(self.router.backends)
        ) - 1
        
        backend = self.router.backends[backend_idx]
        
        print(f"\n{c.BOLD}Available Statuses:{c.RESET}")
        print(f"1. {c.GREEN}Healthy{c.RESET}")
        print(f"2. {c.YELLOW}Degraded{c.RESET}")
        print(f"3. {c.RED}Down{c.RESET}")
        
        status_idx = self.get_user_choice("Select a new status (1-3): ", default=1, max_value=3)
        
        status_map = {1: "healthy", 2: "degraded", 3: "down"}
        new_status = status_map[status_idx]
        
        self.router.update_backend_status(backend.backend_id, new_status)
        print(f"{c.GREEN}Backend {backend.backend_id} status updated to {new_status}{c.RESET}")
        
        # Also allow updating load
        if self.get_yes_no_input("Update backend load? (y/n): ", default=False):
            try:
                load = float(input("Enter new load percentage (0-100): ") or "50")
                load = max(0.0, min(100.0, load))
                queue_time = int(load * 0.5)  # Simple estimation
                
                self.router.update_backend_load(backend.backend_id, load, queue_time)
                print(f"{c.GREEN}Backend {backend.backend_id} load updated to {load:.1f}%{c.RESET}")
            except ValueError:
                print(f"{c.RED}Invalid input. Load not updated.{c.RESET}")
    
    def simulate_backend_fluctuation(self):
        """Simulate random changes in backend statuses."""
        c = ColorFormatter
        print(f"{c.YELLOW}Simulating random backend status changes...{c.RESET}")
        changes = self.router.simulate_backend_degradation()
        
        if changes:
            print(f"{c.BOLD}Status Changes:{c.RESET}")
            for backend_id, old_status, new_status in changes:
                old_color = c.GREEN if old_status == "healthy" else (c.YELLOW if old_status == "degraded" else c.RED)
                new_color = c.GREEN if new_status == "healthy" else (c.YELLOW if new_status == "degraded" else c.RED)
                
                print(f"Backend {backend_id}: {old_color}{old_status}{c.RESET} -> {new_color}{new_status}{c.RESET}")
        else:
            print(f"{c.YELLOW}No changes occurred in this fluctuation.{c.RESET}")
    
    def modify_request_parameters(self):
        """Create or modify an inference request with custom parameters."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}Create/Modify Request Parameters:{c.RESET}")
        print("1. Modify existing request")
        print("2. Create new request")
        
        choice = self.get_user_choice("Select option: ", default=1, max_value=2)
        
        if choice == 1:
            # Modify existing request
            print(f"\n{c.BOLD}Available Requests:{c.RESET}")
            for i, req in enumerate(self.requests):
                compliance_str = ', '.join(req.compliance_constraints) if req.compliance_constraints else "None"
                print(f"{i+1}. {req.model_name} ({req.input_token_size} tokens, {req.required_latency_ms}ms SLA, Compliance: {compliance_str})")
            
            req_idx = self.get_user_choice(
                f"Select a request to modify (1-{len(self.requests)}): ", 
                default=1, 
                max_value=len(self.requests)
            ) - 1
            
            request = self.requests[req_idx]
            
            # Create modified request with the same parameters initially
            model_name = request.model_name
            input_token_size = request.input_token_size
            required_latency_ms = request.required_latency_ms
            compliance_constraints = request.compliance_constraints.copy()
            priority = request.priority
            max_cost = request.max_cost
            prefer_cost_over_latency = request.prefer_cost_over_latency
        else:
            # Create new request
            # Default values
            model_name = "llama-3-70b"
            input_token_size = 1024
            required_latency_ms = 200
            compliance_constraints = set()
            priority = 1
            max_cost = None
            prefer_cost_over_latency = False
        
        # Let user modify parameters
        print(f"\n{c.BOLD}Configure Request Parameters:{c.RESET}")
        
        # Model name
        print(f"{c.BOLD}Available Models:{c.RESET}")
        models = set()
        for backend in self.router.backends:
            models.update(backend.supported_models)
        
        for i, model in enumerate(sorted(models)):
            print(f"{i+1}. {model}")
        
        model_idx = self.get_user_choice(
            f"Select model (1-{len(models)}) [{model_name}]: ", 
            default=list(sorted(models)).index(model_name) + 1 if model_name in models else 1,
            max_value=len(models)
        ) - 1
        
        model_name = list(sorted(models))[model_idx]
        
        # Input token size
        try:
            input_str = input(f"Input token size (100-65536) [{input_token_size}]: ")
            if input_str.strip():
                input_token_size = int(input_str)
                input_token_size = max(100, min(65536, input_token_size))
        except ValueError:
            print(f"{c.YELLOW}Invalid input. Using {input_token_size} tokens.{c.RESET}")
        
        # Latency SLA
        try:
            latency_str = input(f"Required latency in ms (20-2000) [{required_latency_ms}]: ")
            if latency_str.strip():
                required_latency_ms = int(latency_str)
                required_latency_ms = max(50, min(2000, required_latency_ms))
        except ValueError:
            print(f"{c.YELLOW}Invalid input. Using {required_latency_ms}ms.{c.RESET}")
        
        # Compliance constraints
        print(f"\n{c.BOLD}Compliance Constraints:{c.RESET}")
        all_tags = set()
        for backend in self.router.backends:
            all_tags.update(backend.compliance_tags)
        
        print("Current constraints:", ", ".join(compliance_constraints) if compliance_constraints else "None")
        print("Available tags:", ", ".join(all_tags))
        
        print("\nEnter tags separated by commas, or 'none' to clear constraints")
        compliance_input = input(f"Compliance constraints: ")
        
        if compliance_input.lower() == 'none':
            compliance_constraints = set()
        elif compliance_input.strip():
            compliance_constraints = {tag.strip() for tag in compliance_input.split(',')}
        
        # Priority
        try:
            priority_str = input(f"Priority (1-5, lower is higher priority) [{priority}]: ")
            if priority_str.strip():
                priority = int(priority_str)
                priority = max(1, min(5, priority))
        except ValueError:
            print(f"{c.YELLOW}Invalid input. Using priority {priority}.{c.RESET}")
        
        # Max cost
        print(f"Current max cost: ${max_cost if max_cost is not None else 'Not specified'}")
        try:
            cost_str = input(f"Maximum cost in USD (or 'none' for no limit): ")
            if cost_str.lower() == 'none':
                max_cost = None
            elif cost_str.strip():
                max_cost = float(cost_str)
                max_cost = max(0.0, max_cost)
        except ValueError:
            print(f"{c.YELLOW}Invalid input. Using previous max cost.{c.RESET}")
        
        # Cost vs latency preference
        cost_pref_str = input(f"Prefer cost over latency? (y/n) [{'y' if prefer_cost_over_latency else 'n'}]: ")
        if cost_pref_str.strip():
            prefer_cost_over_latency = cost_pref_str.lower().startswith('y')
        
        # Create the modified/new request
        modified_request = InferenceRequest(
            model_name=model_name,
            input_token_size=input_token_size,
            required_latency_ms=required_latency_ms,
            compliance_constraints=compliance_constraints,
            priority=priority,
            max_cost=max_cost,
            prefer_cost_over_latency=prefer_cost_over_latency,
            unique_id=f"custom_req_{int(time.time())}" if choice == 2 else request.unique_id
        )
        
        # If modifying existing, replace it, otherwise add new
        if choice == 1:
            self.requests[req_idx] = modified_request
            print(f"{c.GREEN}Request modified successfully.{c.RESET}")
        else:
            self.requests.append(modified_request)
            print(f"{c.GREEN}New request created successfully.{c.RESET}")
        
        # Option to immediately test the request
        if self.get_yes_no_input("Test this request now? (y/n): ", default=True):
            result = self.router.route_request(modified_request, self.user_region)
            formatted_result = result.to_dict()
            RoutingVisualizer.print_routing_decision(formatted_result)
            RoutingVisualizer.visualize_routing_path(formatted_result, self.user_region)
            
            # Store result for statistics
            self.routing_results.append(result)
    
    def get_routing_recommendations(self):
        """Get routing recommendations for specific requirements."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}Get Routing Recommendations:{c.RESET}")
        
        # Select model
        print(f"\n{c.BOLD}Available Models:{c.RESET}")
        models = set()
        for backend in self.router.backends:
            models.update(backend.supported_models)
        
        for i, model in enumerate(sorted(models)):
            print(f"{i+1}. {model}")
        
        model_idx = self.get_user_choice(
            f"Select model (1-{len(models)}): ", 
            default=1,
            max_value=len(models)
        ) - 1
        
        model_name = list(sorted(models))[model_idx]
        
        # Latency requirement
        try:
            latency_ms = int(input("Required latency in ms (20-2000): ") or "200")
            latency_ms = max(50, min(2000, latency_ms))
        except ValueError:
            latency_ms = 200
            print(f"{c.YELLOW}Invalid input. Using 200ms.{c.RESET}")
        
        # Compliance constraints
        print(f"\n{c.BOLD}Compliance Constraints:{c.RESET}")
        all_tags = set()
        for backend in self.router.backends:
            all_tags.update(backend.compliance_tags)
        
        print("Available tags:", ", ".join(all_tags))
        print("Enter tags separated by commas, or leave empty for no constraints")
        
        compliance_input = input("Compliance constraints: ")
        compliance_constraints = []
        
        if compliance_input.strip():
            compliance_constraints = [tag.strip() for tag in compliance_input.split(',')]
        
        # Get recommendations
        recommendations = self.router.get_routing_recommendations(
            model_name=model_name,
            required_latency_ms=latency_ms,
            compliance_constraints=compliance_constraints,
            from_region=self.user_region
        )
        
        # Display recommendations
        print(f"\n{c.BOLD}{c.CYAN}Tesseract Routing Recommendations{c.RESET}\n")
        
        print(f"{c.BOLD}Request Profile:{c.RESET}")
        print(f"  Model: {recommendations['request_profile']['model']}")
        print(f"  Required Latency: {recommendations['request_profile']['required_latency_ms']} ms")
        print(f"  Compliance Constraints: {', '.join(recommendations['request_profile']['compliance_constraints']) or 'None'}")
        print(f"  From Region: {recommendations['request_profile']['from_region']}")
        
        if recommendations['can_route']:
            recommended = recommendations['recommended_backend']
            print(f"\n{c.GREEN}{c.BOLD}✓ This request can be routed successfully{c.RESET}")
            print(f"  {c.BOLD}Recommended Backend:{c.RESET} {recommended['chip_type']} in {recommended['region']}")
            print(f"  Backend ID: {recommended['backend_id']}")
            print(f"  Estimated Latency: {recommended['estimated_latency_ms']} ms")
            print(f"  Estimated Cost: ${recommended['estimated_cost']:.6f}")
            
            if recommendations.get('alternatives'):
                print(f"\n{c.BOLD}Alternative Backends:{c.RESET}")
                for alt in recommendations['alternatives']:
                    sla_met = "✓" if alt['meets_sla'] else "✗"
                    sla_color = c.GREEN if alt['meets_sla'] else c.RED
                    print(f"  {sla_color}{sla_met} {alt['chip_type']} in {alt['region']}{c.RESET}")
                    print(f"    Backend ID: {alt['backend_id']}")
                    print(f"    Estimated Latency: {alt['estimated_latency_ms']} ms")
                    print(f"    Estimated Cost: ${alt['estimated_cost']:.6f}")
        else:
            print(f"\n{c.RED}{c.BOLD}✗ This request cannot be routed successfully{c.RESET}")
            
            if 'routing_failure_analysis' in recommendations:
                analysis = recommendations['routing_failure_analysis']
                print(f"\n{c.BOLD}Failure Analysis:{c.RESET}")
                print(f"  Filtered Backends: {analysis['filtered_backends_count']}")
                
                print(f"  Common Reasons:")
                for reason, count in analysis['common_reasons'].items():
                    print(f"    - {reason} ({count} backends)")
            
            if 'suggestions' in recommendations:
                print(f"\n{c.BOLD}Suggestions:{c.RESET}")
                for suggestion in recommendations['suggestions']:
                    print(f"  - {suggestion}")
    
    def change_user_region(self):
        """Change the simulated user region."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}Change User Region:{c.RESET}")
        print(f"Current region: {self.user_region}")
        
        # Get all available regions
        available_regions = set()
        for backend in self.router.backends:
            available_regions.add(backend.region)
        
        # Add regions from latency map for completeness
        for region in self.router.network_latency.latency_map.keys():
            available_regions.add(region)
        
        # Sort and display regions
        regions_list = sorted(available_regions)
        for i, region in enumerate(regions_list):
            print(f"{i+1}. {region}")
        
        region_idx = self.get_user_choice(
            f"Select region (1-{len(regions_list)}): ", 
            default=regions_list.index(self.user_region) + 1 if self.user_region in regions_list else 1,
            max_value=len(regions_list)
        ) - 1
        
        self.user_region = regions_list[region_idx]
        self.router.set_user_region(self.user_region)
        
        print(f"{c.GREEN}User region changed to {self.user_region}{c.RESET}")
        
        # Display the latency map to show how this affects routing
        self.view_latency_map()
    
    def run(self):
        """Run the main CLI interface loop."""
        c = ColorFormatter
        
        print(f"\n{c.BOLD}{c.CYAN}Tesseract AI Inference Router{c.RESET}")
        print("=========================================")
        print("A chip-agnostic, latency-aware routing layer for real-time AI inference")
        print(f"User Region: {self.user_region}")
        print()
        
        while True:
            self.display_menu()
            
            choice = self.get_user_choice("\nSelect an option: ", default=1, max_value=11)
            
            if choice == 1:
                self.route_single_request()
            elif choice == 2:
                self.route_multiple_requests()
            elif choice == 3:
                self.view_cluster_health()
            elif choice == 4:
                self.view_latency_map()
            elif choice == 5:
                self.view_system_statistics()
            elif choice == 6:
                self.toggle_backend_status()
            elif choice == 7:
                self.simulate_backend_fluctuation()
            elif choice == 8:
                self.modify_request_parameters()
            elif choice == 9:
                self.get_routing_recommendations()
            elif choice == 10:
                self.change_user_region()
            elif choice == 11:
                print(f"\n{c.GREEN}{c.BOLD}Thank you for using Tesseract!{c.RESET}")
                break


class TesseractDashboard:
    """Web-based dashboard for the Tesseract router."""
    
    def __init__(self, router: TesseractRouter, requests: List[InferenceRequest], args):
        """Initialize the dashboard with a router and request list."""
        self.router = router
        self.requests = requests
        self.args = args
    
    def run(self):
        """Run the dashboard."""
        try:
            from flask import Flask, render_template, request, jsonify
            print(f"{ColorFormatter.GREEN}Starting Tesseract Dashboard...{ColorFormatter.RESET}")
            print(f"{ColorFormatter.YELLOW}Dashboard mode is still under development.{ColorFormatter.RESET}")
            print(f"{ColorFormatter.YELLOW}Falling back to CLI mode...{ColorFormatter.RESET}")
            return False
        except ImportError:
            print(f"{ColorFormatter.RED}Dashboard mode requires Flask to be installed.{ColorFormatter.RESET}")
            print("To install Flask: pip install flask")
            print(f"{ColorFormatter.YELLOW}Falling back to CLI mode...{ColorFormatter.RESET}")
            return False
        return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Tesseract AI Inference Router')
    parser.add_argument('--dashboard', action='store_true', help='Start the dashboard UI')
    parser.add_argument('--fluctuate', action='store_true', help='Enable backend fluctuation')
    parser.add_argument('--frequency', type=int, default=5, help='Fluctuation frequency in seconds')
    parser.add_argument('--region', type=str, default='us-east-1', help='User region for latency calculations')
    return parser.parse_args()


def fluctuation_monitor(router: TesseractRouter, frequency: int):
    """
    Start a background thread to periodically simulate backend fluctuations.
    
    Args:
        router: The router instance to affect
        frequency: How often to fluctuate in seconds
    """
    def fluctuate_periodically():
        while True:
            router.simulate_backend_degradation()
            time.sleep(frequency)
    
    thread = threading.Thread(target=fluctuate_periodically, daemon=True)
    thread.start()
    logger.info(f"Started background fluctuation monitor (frequency: {frequency}s)")


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up the environment
    TesseractInitializer.setup_environment()
    
    # Create router and load defaults
    logger.info("Initializing Tesseract Router...")
    router = TesseractRouter(
        backends_file="models/backends.json",
        latency_file="configs/latency_map.json",
        user_region=args.region
    )
    
    # Load all available requests
    requests = load_all_requests()
    
    # Start fluctuation monitor if requested
    if args.fluctuate:
        fluctuation_monitor(router, args.frequency)
    
    # Launch the appropriate interface
    if args.dashboard:
        dashboard = TesseractDashboard(router, requests, args)
        if not dashboard.run():
            # Fall back to CLI if dashboard fails to start
            cli = TesseractCLI(router, requests, args)
            cli.run()
    else:
        # Run the CLI interface
        cli = TesseractCLI(router, requests, args)
        cli.run()


if __name__ == "__main__":
    main()