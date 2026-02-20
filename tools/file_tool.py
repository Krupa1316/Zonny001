"""
FileTool - Read files from the workspace

Provides file reading capabilities for codebase analysis.
"""

from runtime.base import BaseTool
from pathlib import Path


class FileTool(BaseTool):
    """
    File reading tool for accessing workspace files.
    
    Can read text files, Python files, YAML files, etc.
    """
    
    name = "file_read"
    
    def __init__(self, workspace_root: str = "."):
        """
        Initialize file tool.
        
        Args:
            workspace_root: Root directory for file operations
        """
        self.workspace_root = Path(workspace_root).resolve()
    
    def execute(self, input_text: str) -> str:
        """
        Read a file.
        
        Args:
            input_text: File path (relative to workspace root)
            
        Returns:
            File contents or error message
        """
        try:
            # Parse input (could be just path or "read <path>")
            file_path = input_text.strip()
            if file_path.startswith("read "):
                file_path = file_path[5:].strip()
            
            # Resolve path
            full_path = (self.workspace_root / file_path).resolve()
            
            # Security check: ensure path is within workspace
            if not str(full_path).startswith(str(self.workspace_root)):
                return f"Access denied: path outside workspace"
            
            # Check if file exists
            if not full_path.exists():
                return f"File not found: {file_path}"
            
            if not full_path.is_file():
                return f"Not a file: {file_path}"
            
            # Read file
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Limit size
            max_size = 5000
            if len(content) > max_size:
                content = content[:max_size] + f"\n\n... (truncated, {len(content)} total chars)"
            
            return f"=== File: {file_path} ===\n\n{content}"
            
        except UnicodeDecodeError:
            return f"Cannot read file (binary or encoding issue): {input_text}"
        except Exception as e:
            return f"File read error: {e}"
    
    def __repr__(self):
        return f"FileTool(name='{self.name}', root='{self.workspace_root}')"
