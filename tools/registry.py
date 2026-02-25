"""
Slice D - Tool Registry

Dynamic tool registration and lookup.

Similar to agent registry, but for tools.

Design:
- Simple dict-based registry
- Register tools at import time
- Get tool by name
- List all available tools
- Permission layer (allowed tools only)
"""

# Global registry
TOOLS = {}

# Security: Only these tools are allowed
ALLOWED_TOOLS = {
    "read_file",
    "write_file",
    "list_files",
    "search_files",
    "run_shell",
    "get_cwd",
}


def register(name: str, func):
    """
    Register a tool function.
    
    Args:
        name: Tool name
        func: Tool function
    """
    if not callable(func):
        raise ValueError("Tool must be callable")
    
    TOOLS[name] = func
    # Silent registration to avoid encoding issues on Windows
    # print(f"[FIX] Registered tool: {name}")


def get(name: str):
    """
    Get tool by name.
    
    Args:
        name: Tool name
        
    Returns:
        Tool function or None
        
    Raises:
        PermissionError: If tool not in allowed list
    """
    if name not in ALLOWED_TOOLS:
        raise PermissionError(f"Tool '{name}' not in allowed list")
    
    return TOOLS.get(name)


def list_tools():
    """
    List all registered and allowed tools.
    
    Returns:
        List of tool names that are both registered and allowed
    """
    return [name for name in TOOLS.keys() if name in ALLOWED_TOOLS]


def is_allowed(name: str) -> bool:
    """
    Check if tool is allowed.
    
    Args:
        name: Tool name
        
    Returns:
        True if allowed
    """
    return name in ALLOWED_TOOLS


def get_all():
    """
    Get all registered tools.
    
    Returns:
        Dict of {name: func}
    """
    return TOOLS.copy()
