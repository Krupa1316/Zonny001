"""
Tools package

Slice D: Tool Invocation Layer
- Registry (dynamic tool registration)
- Filesystem tools (read, write, list, search)
- Shell tools (safe command execution)
- Tool runner (execution engine)

Phase 3 (legacy):
- VectorTool, FileTool, MemoryTool (still available)
"""

# Slice D - Import and register tools
from .registry import register
from .fs import read_file, write_file, list_files, search_files, get_cwd
from .shell import run_shell

# Initialize silently (avoid emoji encoding issues on Windows)
# print("\n🔧 Initializing Slice D Tool System...")

# Register filesystem tools
register("read_file", read_file)
register("write_file", write_file)
register("list_files", list_files)
register("search_files", search_files)
register("get_cwd", get_cwd)

# Register shell tools
register("run_shell", run_shell)

# print("✅ Slice D Tool System Ready\n")

# Phase 3 (legacy) - Import all legacy tools
from .vector_tool import VectorTool
from .file_tool import FileTool
from .memory_tool import MemoryTool

__all__ = [
    # Slice D
    'register',
    'read_file',
    'write_file',
    'list_files',
    'search_files',
    'get_cwd',
    'run_shell',
    # Legacy
    'VectorTool',
    'FileTool',
    'MemoryTool',
]
