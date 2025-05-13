#!/usr/bin/env python3
"""
Test script to check which imports work with the current router.py implementation.
This helps diagnose import issues without running the full application.
"""

print("Attempting to import from router.py...")

try:
    print("Trying to import TesseractRouter...")
    from tesseract_router import TesseractRouter
    print("✅ Successfully imported TesseractRouter")
except ImportError as e:
    print(f"❌ Failed to import TesseractRouter: {e}")

try:
    print("Trying to import InferenceRequest...")
    from tesseract_router import InferenceRequest
    print("✅ Successfully imported InferenceRequest")
except ImportError as e:
    print(f"❌ Failed to import InferenceRequest: {e}")

try:
    print("Trying to import Backend...")
    from tesseract_router import Backend
    print("✅ Successfully imported Backend")
except ImportError as e:
    print(f"❌ Failed to import Backend: {e}")

try:
    print("Trying to import BackendStatus...")
    from tesseract_router import BackendStatus
    print("✅ Successfully imported BackendStatus")
except ImportError as e:
    print(f"❌ Failed to import BackendStatus: {e}")

try:
    print("Trying to import load_all_requests...")
    from tesseract_router import load_all_requests
    print("✅ Successfully imported load_all_requests")
except ImportError as e:
    print(f"❌ Failed to import load_all_requests: {e}")

print("\nChecking router.py content for BackendStatus definition...")
import os

if os.path.exists("router.py"):
    with open("router.py", "r") as f:
        content = f.read()
    
    if "class BackendStatus" in content:
        print("✅ Found BackendStatus class definition in router.py")
    else:
        print("❌ BackendStatus class definition not found in router.py")
        
        if "BackendStatus" in content:
            print("   However, 'BackendStatus' is mentioned in the file")
        
        # Look for status field definition in Backend class
        if "status:" in content:
            start_idx = content.find("status:")
            line_end = content.find("\n", start_idx)
            status_line = content[start_idx:line_end].strip()
            print(f"   Found status field definition: {status_line}")
else:
    print("❌ router.py file not found!")

print("\nRecommendation:")
print("If BackendStatus is missing, you can:")
print("1. Run the simplified_main.py script which includes fallbacks")
print("2. Update your router.py to include the BackendStatus enum")
print("3. Add 'from enum import Enum' and create the BackendStatus enum in your main.py")