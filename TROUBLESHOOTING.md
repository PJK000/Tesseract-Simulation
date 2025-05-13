# Tesseract Troubleshooting Guide

This guide helps you resolve common issues with the Tesseract AI Inference Router.

## Import Errors

### Issue: Cannot import `BackendStatus` from router

```
ImportError: cannot import name 'BackendStatus' from 'router'
```

**Solution 1**: Verify your router.py file was properly updated with our refactored version which includes the BackendStatus enum.

1. Check that the refactored router.py has been saved to your project directory:
   ```bash
   cat router.py | grep -A 10 "BackendStatus"
   ```

2. If it doesn't show the BackendStatus enum, manually copy the content from our refactored version.

**Solution 2**: Use the version-compatible import in main.py:

1. Update your main.py import line to:
   ```python
   from router import TesseractRouter, InferenceRequest, Backend, load_all_requests
   # Import BackendStatus if it exists, otherwise create a compatible enum
   try:
       from router import BackendStatus
   except ImportError:
       from enum import Enum
       
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
   ```

### Issue: Missing module errors

```
ModuleNotFoundError: No module named 'utils.scoring'
```

**Solution**:

1. Run the installation check script to verify your setup:
   ```bash
   python check_installation.py
   ```

2. Make sure all the required files and directories exist:
   ```bash
   mkdir -p utils tests
   touch utils/__init__.py tests/__init__.py
   ```

3. Ensure that the scoring.py file is properly installed in the utils directory:
   ```bash
   # Check if the file exists and has content
   cat utils/scoring.py
   
   # If empty or missing, you need to recreate it from our refactored version
   ```

## File Structure Issues

### Issue: Directory structure is incorrect

**Solution**:

1. Verify that you have the correct directory structure:
   ```bash
   find . -type f -name "*.py" | sort
   ```

2. You should see at least:
   ```
   ./check_installation.py
   ./main.py
   ./router.py
   ./tests/__init__.py
   ./tests/test_router.py
   ./utils/__init__.py
   ./utils/scoring.py
   ```

3. If not, create the missing directories and files:
   ```bash
   mkdir -p models utils tests
   touch utils/__init__.py tests/__init__.py
   ```

## Complete Reinstallation

If you continue to face issues, a complete reinstallation might be helpful:

1. Make a backup of your current implementation:
   ```bash
   mkdir -p backup
   cp -r * backup/
   ```

2. Create a fresh implementation using our refactored files:
   ```bash
   # Create the directory structure
   mkdir -p utils tests models
   
   # Create empty __init__.py files
   touch utils/__init__.py tests/__init__.py
   ```

3. Copy the content of each refactored file into the corresponding local file.

## Running the Installation Check

We've provided a check_installation.py script that verifies your installation:

```bash
python check_installation.py
```

This script checks for:
- Required files and directories
- Proper import functionality
- Python version compatibility

## Getting Additional Help

If you continue to encounter issues:

1. Check that your Python version is 3.6 or higher:
   ```bash
   python --version
   ```

2. Ensure you have no conflicting modules with the same names:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

3. Try running with verbose logging enabled:
   ```bash
   python -v main.py
   ```

4. If the issue persists, provide the output of the installation check along with any error messages.