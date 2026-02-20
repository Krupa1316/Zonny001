"""
Slice E - Workspace Awareness

Provides project context to agents:
- File tree scanning
- Git status
- Project structure analysis

This gives agents "eyes" into the workspace.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def scan_workspace(max_depth: int = 2, max_files: int = 100, root: str = None) -> Dict:
    """
    Scan workspace and return structured info.
    
    Args:
        max_depth: Maximum directory depth to scan
        max_files: Maximum files to include
        root: Project root directory (defaults to cwd)
        
    Returns:
        Dict with workspace structure
    """
    workspace = Path(root).resolve() if root else Path.cwd()
    
    # Get top-level structure
    files = []
    directories = []
    
    try:
        for item in workspace.iterdir():
            # Skip common ignore patterns
            if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules', 'venv', '.venv']:
                continue
            
            if item.is_dir():
                directories.append(item.name)
            elif item.is_file():
                files.append(item.name)
                
            if len(files) + len(directories) >= max_files:
                break
                
    except Exception as e:
        return {"error": str(e)}
    
    return {
        "workspace": str(workspace),
        "files": sorted(files),
        "directories": sorted(directories),
        "total_files": len(files),
        "total_dirs": len(directories)
    }


def get_file_tree(directory: str = ".", max_depth: int = 2, root: str = None) -> str:
    """
    Get formatted file tree.
    
    Args:
        directory: Directory to scan
        max_depth: Maximum depth
        root: Project root directory (defaults to cwd)
        
    Returns:
        Formatted tree string
    """
    workspace = Path(root).resolve() if root else Path.cwd().resolve()
    path = (workspace / directory).resolve() if not Path(directory).is_absolute() else Path(directory).resolve()

    # Security: Stay in workspace (cross-platform)
    try:
        path.relative_to(workspace)
    except ValueError:
        return "❌ Access denied: Outside workspace"
    
    tree_lines = []
    
    def add_items(current_path: Path, prefix: str = "", depth: int = 0):
        if depth >= max_depth:
            return
            
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            
            for i, item in enumerate(items):
                # Skip common ignore patterns
                if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules', 'venv', '.venv', 'chroma_memory']:
                    continue
                
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                
                if item.is_dir():
                    tree_lines.append(f"{prefix}{current_prefix}📁 {item.name}/")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    add_items(item, next_prefix, depth + 1)
                else:
                    tree_lines.append(f"{prefix}{current_prefix}📄 {item.name}")
                    
                if len(tree_lines) > 100:  # Limit output
                    break
                    
        except PermissionError:
            tree_lines.append(f"{prefix}❌ Permission denied")
    
    tree_lines.append(f"📁 ./ (workspace root)")
    add_items(path)
    
    return "\n".join(tree_lines)


def git_status(root: str = None) -> Dict:
    """
    Get git repository status.
    
    Args:
        root: Project root directory (defaults to cwd)
    
    Returns:
        Dict with git info or empty if not a git repo
    """
    cwd = root if root else os.getcwd()
    
    try:
        # Check if git repo
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            timeout=2,
            cwd=cwd
        )
        
        # Get branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=cwd
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get status
        status_result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=cwd
        )
        status = status_result.stdout.strip() if status_result.returncode == 0 else ""
        
        # Count changes
        changes = len(status.split('\n')) if status else 0
        
        return {
            "is_git_repo": True,
            "branch": branch,
            "changes": changes,
            "status": status[:500] if status else "Clean working tree"
        }
        
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return {
            "is_git_repo": False
        }


def get_workspace_summary() -> str:
    """
    Get human-readable workspace summary.
    
    Returns:
        Formatted workspace summary
    """
    workspace_info = scan_workspace()
    git_info = git_status()
    
    summary = f"""📁 Workspace Summary
{"="*50}

Location: {workspace_info.get('workspace', 'unknown')}
Files: {workspace_info.get('total_files', 0)}
Directories: {workspace_info.get('total_dirs', 0)}
"""
    
    if git_info.get('is_git_repo'):
        summary += f"""
Git Branch: {git_info.get('branch', 'unknown')}
Changes: {git_info.get('changes', 0)} modified files
"""
    else:
        summary += "\nNot a git repository\n"
    
    return summary


def get_project_context() -> Dict:
    """
    Get comprehensive project context for agents.
    
    Returns:
        Dict with all workspace info
    """
    return {
        "workspace": scan_workspace(),
        "git": git_status(),
        "cwd": os.getcwd(),
        "tree": get_file_tree(max_depth=2)
    }
