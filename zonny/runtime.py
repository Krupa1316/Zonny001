"""
Zonny Runtime - Local Agent Bootstrap

This file starts the Zonny agent loop in the current working directory.
It's the bridge between the CLI and the agent system.

Key insight:
- CLI captures os.getcwd() (where user typed 'zonny')
- Runtime passes that as project_root to everything
- All tools operate relative to project_root

This is exactly what Claude Code and Gemini CLI do.
"""

import os
from zonny.agent import loop


def start(project_root: str):
    """
    Start Zonny agent in the specified project root.
    
    Args:
        project_root: Absolute path to the directory where 'zonny' was invoked
    """
    print(f"🚀 Zonny initialized in: {project_root}")
    print(f"📁 Working directory: {os.path.basename(project_root)}")
    print()
    
    # Start the agent loop
    loop(project_root)
