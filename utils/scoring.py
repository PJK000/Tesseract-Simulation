"""
Tesseract Scoring Utilities

This module contains utilities for scoring backends and visualizing 
routing decisions. It supports the router's core decision-making process
and provides helpful visualization functions for terminal output.
"""

from typing import Dict, List, Any, Optional
from dataclasses import asdict
import json


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
    
    @classmethod
    def status_text(cls, status: str) -> str:
        """Get a colored text representation of a status."""
        if status == "healthy":
            return f"{cls.GREEN}{cls.BOLD}Healthy{cls.RESET}"
        elif status == "degraded":
            return f"{cls.YELLOW}{cls.BOLD}Degraded{cls.RESET}"
        else:  # down
            return f"{cls.RED}{cls.BOLD}Down{cls.RESET}"
    
    @classmethod
    def status_symbol(cls, status: str) -> str:
        """Get an emoji/symbol representation of a status."""
        if status == "healthy":
            return "✓"
        elif status == "degraded":
            return "!"
        else:  # down
            return "✗"
    
    @staticmethod
    def status_color(status: str) -> str:
        """Get the appropriate color formatting for a status."""
        if status == "healthy":
            return ColorFormatter.GREEN
        elif status == "degraded":
            return ColorFormatter.YELLOW
        else:  # down
            return ColorFormatter.RED


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
        print(f"  Compliance: {compliance_text}")
        print(f"  Priority: {req_info['priority']}")
        
        # Print decision
        print(f"\n{c.BOLD}Routing Decision:{c.RESET}")
        if "error" in decision["decision"]:
            print(f"  {c.RED}{c.BOLD}Error: {decision['decision']['error']}{c.RESET}")
        else:
            selected = decision["decision"]
            print(f"  Selected: {c.BOLD}{c.CYAN}{selected['chip_type']}{c.RESET} in {c.GREEN}{selected['region']}{c.RESET}")
            print(f"  Backend ID: {selected['selected_backend_id']}")
            print(f"  Status: {c.status_text(selected['status'])}")
            print(f"  Score: {selected['score']:.6f}")
            print(f"  Expected Latency: {c.BOLD}{selected['final_latency_ms']} ms{c.RESET}")
            print(f"  Total Cost: ${selected['final_cost']:.6f}")
            
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
                print(f"  {backend['id']} - {backend['chip']} in {backend['region']} - {c.status_text(backend['status'])}")
        
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
        print(f"\n{c.BOLD}{c.CYAN}Cluster Health Heatmap{c.RESET}\n")
        
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
                    
                    status_text = f"{c.status_color(status)}■ {status.capitalize()}{c.RESET}"
                    print(status_text.center(chip_widths[chip]), end="")
                else:
                    print("-".center(chip_widths[chip]), end="")
            
            print()
        
        print()
    
    @staticmethod
    def visualize_routing_path(result: Dict[str, Any]) -> None:
        """
        Visualize the routing path for a request using ASCII art.
        
        Args:
            result: The routing result dictionary
        """
        c = ColorFormatter
        request = result["request_info"]
        
        print(f"\n{c.BOLD}{c.CYAN}Routing Path:{c.RESET}\n")
        
        # Step 1: Request
        print(f"  {c.BOLD}Request{c.RESET}: {request['model']} ({request['input_tokens']} tokens)")
        print("     │")
        print("     ▼")
        
        # Step 2: Router
        print(f"  {c.BOLD}Tesseract Router{c.RESET}")
        print("     │")
        print("     ▼")
        
        # Step 3: Backend Selection
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
            else:
                print(f"  {c.GREEN}{c.BOLD}Selected Backend{c.RESET}: {selected['chip_type']} in {selected['region']}")
        
        print()


class RoutingReport:
    """
    Provides methods for generating reports and analyzing routing decisions.
    This is useful for administrative or dashboard views of the system.
    """
    
    @staticmethod
    def generate_summary(routing_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary of multiple routing decisions.
        
        Args:
            routing_results: List of routing result dictionaries
            
        Returns:
            A dictionary with summary statistics
        """
        total_count = len(routing_results)
        successful_routes = sum(1 for result in routing_results if result["selected_backend"] is not None)
        fallback_routes = sum(1 for result in routing_results if result.get("is_fallback", False))
        
        # Calculate average metrics for successful routes
        total_latency = 0
        total_cost = 0
        backend_usage = {}
        
        for result in routing_results:
            if "decision" in result and "error" not in result["decision"]:
                total_latency += result["decision"]["final_latency_ms"]
                total_cost += result["decision"]["final_cost"]
                
                backend_id = result["decision"]["selected_backend_id"]
                backend_usage[backend_id] = backend_usage.get(backend_id, 0) + 1
        
        avg_latency = total_latency / successful_routes if successful_routes > 0 else 0
        avg_cost = total_cost / successful_routes if successful_routes > 0 else 0
        
        # Find most used backend
        most_used_backend = max(backend_usage.items(), key=lambda x: x[1]) if backend_usage else (None, 0)
        
        return {
            "total_requests": total_count,
            "successful_routes": successful_routes,
            "failed_routes": total_count - successful_routes,
            "fallback_routes": fallback_routes,
            "fallback_percentage": (fallback_routes / successful_routes * 100) if successful_routes > 0 else 0,
            "success_rate": (successful_routes / total_count * 100) if total_count > 0 else 0,
            "avg_latency_ms": avg_latency,
            "avg_cost": avg_cost,
            "most_used_backend": most_used_backend[0],
            "most_used_backend_count": most_used_backend[1],
            "backend_usage": backend_usage
        }
    
    @staticmethod
    def print_summary(summary: Dict[str, Any]) -> None:
        """
        Print a formatted summary report to the console.
        
        Args:
            summary: The summary dictionary from generate_summary
        """
        c = ColorFormatter
        
        print(f"\n{c.BOLD}{c.BLUE}===== TESSERACT ROUTING SUMMARY ====={c.RESET}\n")
        
        print(f"{c.BOLD}Request Statistics:{c.RESET}")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Successful Routes: {summary['successful_routes']} ({summary['success_rate']:.1f}%)")
        print(f"  Failed Routes: {summary['failed_routes']}")
        print(f"  Fallback Routes: {summary['fallback_routes']} ({summary['fallback_percentage']:.1f}% of successful)")
        
        print(f"\n{c.BOLD}Performance Metrics:{c.RESET}")
        print(f"  Average Latency: {summary['avg_latency_ms']:.2f} ms")
        print(f"  Average Cost: ${summary['avg_cost']:.6f}")
        
        print(f"\n{c.BOLD}Backend Usage:{c.RESET}")
        if summary['most_used_backend']:
            print(f"  Most Used Backend: {summary['most_used_backend']} ({summary['most_used_backend_count']} requests)")
        
        if summary['backend_usage']:
            print("  All Backends:")
            for backend_id, count in sorted(summary['backend_usage'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / summary['successful_routes'] * 100) if summary['successful_routes'] > 0 else 0
                print(f"    {backend_id}: {count} requests ({percentage:.1f}%)")
        
        print()