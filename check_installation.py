#!/usr/bin/env python3
"""
Tesseract Installation Checker

This script verifies that all necessary files are correctly installed
and accessible for the Tesseract AI Inference Router to run properly.
"""

import os
import sys
import importlib.util
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TesseractInstallCheck")

def check_file_exists(filepath, create_if_missing=False, content=None):
    """Check if a file exists and optionally create it if missing."""
    path = Path(filepath)
    
    if path.exists():
        logger.info(f"✅ Found {filepath}")
        return True
    else:
        logger.warning(f"❌ Missing {filepath}")
        
        if create_if_missing and content:
            try:
                # Create parent directories if needed
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write content to file
                with open(path, 'w') as f:
                    f.write(content)
                
                logger.info(f"✅ Created {filepath}")
                return True
            except Exception as e:
                logger.error(f"Failed to create {filepath}: {e}")
                return False
        
        return False

def check_module_importable(module_name):
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        logger.info(f"✅ Can import '{module_name}'")
        return True
    except ImportError as e:
        logger.warning(f"❌ Cannot import '{module_name}': {e}")
        return False

def check_directory_exists(dirpath, create_if_missing=False):
    """Check if a directory exists and optionally create it if missing."""
    path = Path(dirpath)
    
    if path.exists() and path.is_dir():
        logger.info(f"✅ Found directory {dirpath}")
        return True
    else:
        logger.warning(f"❌ Missing directory {dirpath}")
        
        if create_if_missing:
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Created directory {dirpath}")
                return True
            except Exception as e:
                logger.error(f"Failed to create directory {dirpath}: {e}")
                return False
        
        return False

def fix_init_files():
    """Ensure __init__.py files exist in all necessary directories."""
    dirs_needing_init = ['utils', 'tests']
    
    for dirpath in dirs_needing_init:
        # Create the directory if it doesn't exist
        check_directory_exists(dirpath, create_if_missing=True)
        
        # Create __init__.py if it doesn't exist
        init_path = os.path.join(dirpath, "__init__.py")
        check_file_exists(init_path, create_if_missing=True, content='"""Tesseract package."""\n')

def main():
    """Run the installation check."""
    logger.info("Starting Tesseract installation check...")
    
    # Check essential directories
    check_directory_exists('models', create_if_missing=True)
    check_directory_exists('utils', create_if_missing=True)
    check_directory_exists('tests', create_if_missing=True)
    
    # Check essential files
    essential_files = [
        'main.py',
        'router.py',
        'utils/scoring.py',
        'utils/__init__.py'
    ]
    
    missing_files = []
    for filepath in essential_files:
        if not check_file_exists(filepath):
            missing_files.append(filepath)
    
    # Fix __init__.py files
    fix_init_files()
    
    # Check if modules can be imported
    modules_to_check = [
        'router',
        'utils.scoring'
    ]
    
    importable = True
    for module in modules_to_check:
        if not check_module_importable(module):
            importable = False
    
    # Summary
    print("\n==== Installation Check Summary ====")
    
    if missing_files:
        print(f"❌ Missing essential files: {', '.join(missing_files)}")
        print("Please make sure all files from the refactored codebase are installed correctly.")
    else:
        print("✅ All essential files present.")
    
    if not importable:
        print("❌ Some modules cannot be imported. Check for Python errors.")
    else:
        print("✅ All modules can be imported.")
    
    # Check for Python version
    print(f"Python version: {sys.version}")
    
    print("\nTo run Tesseract, use: python main.py")
    print("If you encounter any issues, please refer to the README.md file.")

if __name__ == "__main__":
    main()