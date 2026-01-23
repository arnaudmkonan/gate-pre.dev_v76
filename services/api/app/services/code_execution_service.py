import logging
import traceback
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CodeExecutionService:
    """
    Service for executing generated Python mapping code safely.
    
    Implements a restricted execution environment for Path B (Code Mapping).
    """
    
    FORBIDDEN_KEYWORDS = [
        "import os", "from os", "import sys", "from sys", 
        "import subprocess", "from subprocess", "open(", 
        "__import__", "eval(", "exec("
    ]
    
    @staticmethod
    def validate_code_safety(code: str) -> bool:
        """
        Perform static analysis to check for obviously unsafe patterns.
        """
        for keyword in CodeExecutionService.FORBIDDEN_KEYWORDS:
            if keyword in code:
                logger.warning(f"Unsafe code detected: contains forbidden keyword '{keyword}'")
                return False
        return True

    @staticmethod
    def execute_transform(code: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the transformation code on a single record.
        
        Args:
            code: Python code string containing 'transform_record' function
            record: Input record dictionary
            
        Returns:
            Transformed record dictionary
            
        Raises:
            Exception: If execution fails or validation error
        """
        if not CodeExecutionService.validate_code_safety(code):
            raise ValueError("Code validation failed: Unsafe patterns detected")
            
        # Define restricted globals
        # We allow standard types and limit access to builtins
        safe_builtins = {
            "abs": abs, "dict": dict, "int": int, "float": float, 
            "str": str, "list": list, "len": len, "min": min, 
            "max": max, "sum": sum, "round": round, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "set": set,
            "Exception": Exception, "ValueError": ValueError
        }
        
        # We also might want to provide 'datetime', 'decimal', 'json' as convenient imports
        # But 'exec' doesn't auto-import. We can pre-import them and pass in globals.
        import datetime
        import decimal
        import re
        import json
        
        execution_context = {
            "__builtins__": safe_builtins,
            "datetime": datetime,
            "decimal": decimal,
            "re": re,
            "json": json,
            "Decimal": decimal.Decimal
        }
        
        try:
            # compile and exec
            # We wrap it in a try/except for execution
            exec(code, execution_context)
            
            # Check if function exists
            if "transform_record" not in execution_context:
                raise ValueError("Code must define a 'transform_record(record)' function")
            
            transformer = execution_context["transform_record"]
            
            # Run transformation
            result = transformer(record)
            
            if not isinstance(result, dict):
                 raise TypeError(f"Transformation function must return a dict, got {type(result)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            logger.debug(traceback.format_exc())
            raise
