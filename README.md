# Tesseract AI Inference Router

A chip-agnostic AI inference routing platform that intelligently routes AI model inference requests to the most appropriate hardware backends based on multiple factors.

## Overview

Tesseract is a sophisticated routing system for AI inference workloads, designed to:

- Match inference requests with compatible hardware backends
- Optimize for latency, cost, and other requirements
- Handle compliance and geographic constraints
- Provide fallback mechanisms when backends fail
- Visualize routing decisions and backend health

This platform allows organizations to seamlessly mix and match different AI hardware accelerators (GPUs, TPUs, custom ASIC chips) while maintaining high performance and reliability.

## Key Features

- **Intelligent Routing**: Routes requests based on model compatibility, latency SLA, cost efficiency, compliance constraints, and backend health
- **Dynamic Scoring**: Prioritizes backends using a multi-factor scoring system
- **Fallback Handling**: Automatically reroutes requests when backends fail
- **Status Monitoring**: Tracks backend health and visualizes cluster status
- **Simulation Capabilities**: Allows testing of different request patterns and failure scenarios
- **Extensible Framework**: Designed to be easily extended with additional scoring factors and backends

## Architecture

The codebase is organized around these key components:

- **Router Core** (`router.py`): The central routing logic and data structures
- **CLI Interface** (`main.py`): Command-line interface for interacting with the router
- **Visualization Utilities** (`utils/scoring.py`): Functions for visualizing routing decisions and backend health
- **Utility Modules** (`utils/__init__.py`): Common functions for configuration and validation
- **Test Suite** (`tests/test_router.py`): Comprehensive tests for the routing logic

## Setup and Usage

### Installation

1. Clone the repository
2. Ensure Python 3.8+ is installed
3. (Optional) Set up a virtual environment

### Running the CLI

```bash
# Basic CLI mode
python main.py

# Dashboard mode (requires Flask)
python main.py --dashboard

# Enable backend fluctuation (simulates real-world conditions)
python main.py --fluctuate
```

### Running Tests

```bash
# Run all tests
python -m unittest tests/test_router.py

# Run specific test class
python -m unittest tests.test_router.TestTesseractRouter
```

## Design Philosophy and Improvements

The Tesseract codebase has been refactored with these principles in mind:

1. **Modularity**: Each component has a clear, single responsibility
2. **Type Safety**: Enhanced type annotations and validation
3. **Testability**: Code is structured to facilitate unit testing
4. **Extensibility**: New scoring factors, filters, and features can be added without rewriting core logic
5. **Error Handling**: Robust error handling and logging throughout

Key improvements include:

- **Extraction of Scoring Logic**: Moved scoring into a dedicated `BackendScorer` class
- **Filter Pattern**: Created a `BackendFilter` class with method-per-filter design
- **Enum Types**: Used enums for state representations (e.g., `BackendStatus`)
- **Validator Pattern**: Added validation utilities for robust error checking
- **Configuration Management**: Improved config handling with the `ConfigManager` class
- **Comprehensive Testing**: Added unit tests with high coverage
- **CLI Improvements**: Enhanced CLI with better user interaction and error handling
- **Documentation**: Thorough docstrings and README

## Extending the Platform

### Adding New Backend Types

To add a new backend type:

1. Add the backend configuration to `backends.json`
2. Restart the router or reload configurations

### Adding New Scoring Factors

To add new scoring factors:

1. Add methods to the `BackendScorer` class in `router.py`
2. Update the `score_backend` method to include the new factor
3. Update tests to validate the new scoring behavior

### Adding New Filters

To add new compatibility filters:

1. Add methods to the `BackendFilter` class in `router.py`
2. Update the `apply_filters` method to include the new filter
3. Add tests for the new filter

## License

This project is licensed under the MIT License - see the LICENSE file for details.