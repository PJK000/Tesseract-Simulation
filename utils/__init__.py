"""
Tesseract Utilities Package

This package contains utility modules for the Tesseract AI Inference Router.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from pathlib import Path


logger = logging.getLogger("TesseractUtils")


class ConfigManager:
    """Manages configuration files for the Tesseract router."""
    
    @staticmethod
    def load_json_file(file_path: str) -> Any:
        """
        Load and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Parsed JSON content
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file isn't valid JSON
        """
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading JSON from {file_path}: {e}")
            raise
    
    @staticmethod
    def save_json_file(file_path: str, data: Any, indent: int = 2) -> bool:
        """
        Save data to a JSON file.
        
        Args:
            file_path: Path where to save the file
            data: Data to save (must be JSON serializable)
            indent: Number of spaces for indentation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=indent)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {file_path}: {e}")
            return False
    
    @staticmethod
    def merge_configs(base_config: Dict, override_config: Dict) -> Dict:
        """
        Merge two configuration dictionaries.
        
        Args:
            base_config: Base configuration dictionary
            override_config: Override configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        result = base_config.copy()
        
        for key, value in override_config.items():
            # If both values are dictionaries, merge them recursively
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result


class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass


class Validator:
    """Provides validation methods for various data types."""
    
    @staticmethod
    def validate_positive_int(value: int, name: str) -> None:
        """
        Validate that a value is a positive integer.
        
        Args:
            value: Value to validate
            name: Name of the value for error messages
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, int) or value <= 0:
            raise ValidationError(f"{name} must be a positive integer, got {value}")
    
    @staticmethod
    def validate_non_negative_float(value: float, name: str) -> None:
        """
        Validate that a value is a non-negative float.
        
        Args:
            value: Value to validate
            name: Name of the value for error messages
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, (int, float)) or value < 0:
            raise ValidationError(f"{name} must be a non-negative number, got {value}")
    
    @staticmethod
    def validate_string(value: str, name: str, allow_empty: bool = False) -> None:
        """
        Validate that a value is a string.
        
        Args:
            value: Value to validate
            name: Name of the value for error messages
            allow_empty: Whether to allow empty strings
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, str):
            raise ValidationError(f"{name} must be a string, got {type(value).__name__}")
        
        if not allow_empty and not value:
            raise ValidationError(f"{name} cannot be empty")
    
    @staticmethod
    def validate_list(value: List, name: str, allow_empty: bool = True) -> None:
        """
        Validate that a value is a list.
        
        Args:
            value: Value to validate
            name: Name of the value for error messages
            allow_empty: Whether to allow empty lists
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, list):
            raise ValidationError(f"{name} must be a list, got {type(value).__name__}")
        
        if not allow_empty and not value:
            raise ValidationError(f"{name} cannot be empty")
    
    @staticmethod
    def validate_dict(value: Dict, name: str, required_keys: Optional[List[str]] = None) -> None:
        """
        Validate that a value is a dictionary with required keys.
        
        Args:
            value: Value to validate
            name: Name of the value for error messages
            required_keys: List of keys that must be present
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, dict):
            raise ValidationError(f"{name} must be a dictionary, got {type(value).__name__}")
        
        if required_keys:
            missing_keys = [key for key in required_keys if key not in value]
            if missing_keys:
                raise ValidationError(f"{name} is missing required keys: {', '.join(missing_keys)}")


class FileUtils:
    """Utilities for file operations."""
    
    @staticmethod
    def ensure_directory_exists(directory_path: str) -> None:
        """
        Ensure that a directory exists, creating it if necessary.
        
        Args:
            directory_path: Path to the directory
        """
        Path(directory_path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_files_with_extension(directory_path: str, extension: str) -> List[str]:
        """
        Get a list of files with a specific extension in a directory.
        
        Args:
            directory_path: Path to the directory
            extension: File extension to look for (e.g., ".json")
            
        Returns:
            List of file paths
        """
        return [str(f) for f in Path(directory_path).glob(f"*{extension}")]