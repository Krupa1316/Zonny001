"""
Slice E - Command System

Commands are system-level operations (not agent tasks).
They bypass the router and execute directly.

Examples: /agents, /tools, /status, /reset, /new, /save, /load
"""

from .system import handle_system_command

__all__ = ['handle_system_command']
