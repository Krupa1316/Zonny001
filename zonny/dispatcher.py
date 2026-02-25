"""
Zonny Dispatcher - Phase 3: Secure Intent Executor

The ONLY component allowed to touch the OS / filesystem.
Agents reason and plan — Dispatcher alone executes.

Security layers:
  - Registry validation: only known tools can run
  - Workspace root enforcement: no path escapes project_root
  - Extension allow/deny lists for write operations
  - Permission modes: safe (read-only) | dev (read+write) | full
    Set via env var: ZONNY_MODE=safe|dev|full (default: dev)
"""

import os
from tools.fs import read_file, write_file, list_files, search_files
from tools.workspace import scan_workspace, get_file_tree, git_status
from tools.analyzer import create_workspace_report, analyze_workspace, generate_report
from agents.registry import get as get_agent
from commands.system import handle_system_command
from zonny.tool_registry import get_tool_by_name

# ── Permission Mode ────────────────────────────────────────────────────────────
# safe = read-only (no writes ever)
# dev = read + write to allowed extensions (default)
# full = all operations permitted (use with caution)
PERMISSION_MODE = os.environ.get("ZONNY_MODE", "dev").lower()

# Extensions that can be written in dev mode
WRITE_ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".sh", ".env.example"
}

# Extensions that are ALWAYS blocked regardless of mode
WRITE_BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".bin",
    ".env", # real .env files
    ".key", ".pem", ".cert", ".p12" # credentials
}


def _enforce_path_safety(path: str, project_root: str) -> tuple:
    """
    Ensure path stays inside project_root (prevent directory traversal).
    Uses pathlib.relative_to() for correct cross-platform containment.

    Returns:
        (safe_path, error_message)
        safe_path is None when the path is unsafe.
    """
    from pathlib import Path

    if not project_root:
        return path, None

    root = Path(project_root).resolve()

    p = Path(path)
    candidate = (root / p).resolve() if not p.is_absolute() else p.resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"[BLOCKED] Path blocked: '{path}' is outside the workspace root"

    return str(candidate), None


def _check_write_permission(path: str) -> tuple:
    """
    Check whether writing to this path is permitted.

    Returns:
        (allowed: bool, reason: str)
    """
    if PERMISSION_MODE == "safe":
        return False, "[LOCKED] Write blocked: Zonny is running in safe mode (ZONNY_MODE=safe)"

    ext = os.path.splitext(path)[1].lower()

    if ext in WRITE_BLOCKED_EXTENSIONS:
        return False, f"[BLOCKED] Write blocked: '{ext}' files are never allowed"

    # Dotfiles with no extension: block known sensitive names regardless
    basename = os.path.basename(path).lower()
    if basename in (".env", ".secret", ".credentials", ".htpasswd"):
        return False, f"[BLOCKED] Write blocked: '{basename}' is a sensitive dotfile"

    if PERMISSION_MODE == "dev" and ext and ext not in WRITE_ALLOWED_EXTENSIONS:
        return False, f"[BLOCKED] Write blocked: '{ext}' is not in the allowed extension list"

    return True, "ok"


def dispatch(intent: dict, context: dict) -> str:
    """
    Execute a tool intent.

    Args:
        intent: {"tool": "name", "args": {...}}
        context: {"project_root": "...", "session": "...", ...}

    Returns:
        Result string to display.
    """
    tool_name = intent.get("tool")

    # ── Registry Validation ────────────────────────────────────────────────────
    if tool_name and not get_tool_by_name(tool_name):
        return f"[FAIL] Unknown tool: {tool_name} (not in tool registry)"

    args = intent.get("args", {})
    project_root = context.get("project_root", None)

    # ── Filesystem Operations ──────────────────────────────────────────────────
    if tool_name == "filesystem.list":
        path = args.get("path", ".")
        safe_path, err = _enforce_path_safety(path, project_root)
        if err:
            return err
        try:
            result = list_files(path, root=project_root)
            return f"[DIR] Files in {path}:\n\n{result}"
        except Exception as e:
            return f"[FAIL] Error listing files: {e}"

    if tool_name == "filesystem.read":
        path = args.get("path")
        if not path:
            return "[FAIL] Missing required argument: path"
        safe_path, err = _enforce_path_safety(path, project_root)
        if err:
            return err
        try:
            content = read_file(path, root=project_root)
            return f"[DOC] Contents of {path}:\n\n{content[:4000]}"
        except FileNotFoundError:
            # Smart recovery: if path starts with the workspace folder name, strip it
            hint = ""
            if project_root:
                from pathlib import Path as _Path
                folder_name = _Path(project_root).resolve().name
                if path.startswith(folder_name + "/") or path.startswith(folder_name + "\\"):
                    corrected = path[len(folder_name) + 1:]
                    hint = f"\nℹ️ TIP: '{path}' includes the workspace folder name. Try path: '{corrected}' instead."
            return f"[FAIL] File not found: '{path}'{hint}"
        except Exception as e:
            return f"[FAIL] Error reading file: {e}"

    if tool_name == "filesystem.search":
        pattern = args.get("pattern", "*.py")
        directory = args.get("directory", ".")
        safe_path, err = _enforce_path_safety(directory, project_root)
        if err:
            return err
        try:
            result = search_files(pattern, directory, root=project_root)
            return f"[SEARCH] Search results for '{pattern}':\n\n{result}"
        except Exception as e:
            return f"[FAIL] Error searching: {e}"

    if tool_name == "filesystem.write":
        path = args.get("path")
        content = args.get("content", "")
        if not path:
            return "[FAIL] Missing required argument: path"

        # Permission check
        allowed, reason = _check_write_permission(path)
        if not allowed:
            return reason

        # Path safety check
        safe_path, err = _enforce_path_safety(path, project_root)
        if err:
            return err

        # Phase 7: Human confirmation before writing
        try:
            confirm = input(f"\n[WARN]️ Zonny wants to write to '{path}'. Approve? [y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                return f"[STOP] Write to '{path}' cancelled by user."
        except EOFError:
            pass # Non-interactive mode — allow (CI/pipe usage)

        # Smart handling: write to report.txt with no content → generate report
        if (not content or len(content) < 50) and "report" in path.lower():
            try:
                return create_workspace_report(path, detailed=True, root=project_root)
            except Exception as e:
                return f"[FAIL] Error creating report: {e}"

        try:
            result = write_file(path, content, root=project_root)
            return result
        except Exception as e:
            return f"[FAIL] Error writing file: {e}"

    # ── Workspace Operations ───────────────────────────────────────────────────
    if tool_name == "workspace.scan":
        try:
            info = scan_workspace(root=project_root)
            return f"""[DIR] Workspace Overview

Location: {info.get('workspace', 'unknown')}
Files: {info.get('total_files', 0)}
Directories: {info.get('total_dirs', 0)}

Sample files: {', '.join(info.get('files', [])[:10])}"""
        except Exception as e:
            return f"[FAIL] Error scanning workspace: {e}"
    
    if tool_name == "workspace.tree":
        try:
            tree = get_file_tree(max_depth=3, root=project_root)
            return f"[DIR] Project Structure:\n\n{tree}"
        except Exception as e:
            return f"[FAIL] Error getting tree: {e}"
    
    if tool_name == "workspace.report":
        output_file = args.get("output_file", "report.txt")
        try:
            return create_workspace_report(output_file, detailed=True, root=project_root)
        except Exception as e:
            return f"[FAIL] Error creating report: {e}"
    
    # Git operations
    if tool_name == "git.status":
        try:
            git_info = git_status(root=project_root)
            if not git_info.get('is_git_repo'):
                return "[FAIL] Not a git repository"
            return f""" Git Status
            
Branch: {git_info.get('branch', 'unknown')}
Changes: {git_info.get('changes', 0)} files

{git_info.get('status', 'Clean')}"""
        except Exception as e:
            return f"[FAIL] Error getting git status: {e}"
    
    # Code operations - delegate to code agent or fallback
    if tool_name == "code.explain":
        query = args.get("query", "")
        agent = get_agent("code")
        if agent:
            return agent.run(query, context)
        # Fallback: Use filesystem tools to analyze
        return "[IDEA] Code analysis requires the full agent system. However, you can:\n• Use 'list files' to see project structure\n• Use 'read <filename>' to view specific files\n• Use 'workspace.report' for a comprehensive analysis"
    
    if tool_name == "code.analyze":
        file = args.get("file")
        if not file:
            return "[FAIL] Missing required argument: file"
        agent = get_agent("code")
        if agent:
            return agent.run(f"analyze {file}", context)
        # Fallback: Just read the file
        try:
            project_root = context.get("project_root", None)
            content = read_file(file, root=project_root)
            return f"[DOC] Contents of {file}:\n\n{content[:1000]}...\n\n[IDEA] Tip: Full code analysis requires the agent system."
        except Exception as e:
            return f"[FAIL] Error reading file: {e}"
    
    # Document operations - delegate to docs agent or fallback
    if tool_name == "docs.query":
        query = args.get("query", "")
        agent = get_agent("docs")
        if agent:
            return agent.run(query, context)
        # Fallback: Search for README or documentation files
        return " Documentation queries require the full agent system.\n\n[IDEA] Try:\n• 'search *.md' to find markdown files\n• 'read README.md' to view documentation\n• 'list files' to see project structure"
    
    # Memory operations - delegate to memory agent or fallback
    if tool_name == "memory.recall":
        query = args.get("query", "")
        agent = get_agent("memory")
        if agent:
            return agent.run(query, context)
        return "[BRAIN] Memory system requires the agent system with memory.py module."
    
    # System commands
    if tool_name == "system.status":
        cmd_result = handle_system_command("/status", context.get('session'), context)
        return cmd_result.get('response', 'No response')
    
    if tool_name == "system.agents":
        cmd_result = handle_system_command("/agents", context.get('session'), context)
        return cmd_result.get('response', 'No response')
    
    if tool_name == "system.tools":
        cmd_result = handle_system_command("/tools", context.get('session'), context)
        return cmd_result.get('response', 'No response')
    
    if tool_name == "system.help":
        cmd_result = handle_system_command("/help", context.get('session'), context)
        return cmd_result.get('response', 'No response')
    
    # General chat - delegate to general agent or use simple fallback
    if tool_name == "chat.general":
        message = args.get("message", "")
        agent = get_agent("general")
        if agent:
            return agent.run(message, context)
        # Fallback for when memory.py isn't available
        return f"[CHAT] Echo: {message}\n\n(Note: Full chat agent requires memory.py module. Currently operating in minimal mode.)"
    
    # Unknown tool
    return f"[FAIL] Unknown tool: {tool_name}"
