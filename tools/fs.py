"""
Slice D - Filesystem Tools

Tools for file operations.

Security:
- Read-only by default
- Path validation
- No directory traversal
- Workspace-scoped

Tools:
- read_file: Read file contents
- write_file: Write file contents
- list_files: List directory contents
- search_files: Find files by pattern
"""

import os
import platform
from pathlib import Path


def _is_inside(child: Path, parent: Path) -> bool:
    """
    Cross-platform containment check.
    Works on Windows (case-insensitive NTFS) and POSIX (case-sensitive).
    """
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def read_file(path: str, root: str = None) -> str:
    """
    Read file contents with cross-platform encoding resilience.

    Args:
        path: File path (relative or absolute)
        root: Project root directory (defaults to cwd)

    Returns:
        File contents as string
    """
    workspace = Path(root).resolve() if root else Path.cwd().resolve()
    p = Path(path)
    abs_path = (workspace / p).resolve() if not p.is_absolute() else p.resolve()

    # Security: Prevent directory traversal
    if not _is_inside(abs_path, workspace):
        raise PermissionError(f"Access denied: '{path}' is outside workspace")

    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not abs_path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Try multiple encodings — handles UTF-8, UTF-16, Latin-1, Windows-1252
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    last_err: Exception = None
    for enc in encodings:
        try:
            return abs_path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except PermissionError as e:
            # File is locked (Windows) — give a helpful error
            raise PermissionError(
                f"Cannot read '{path}': file is locked by another process. "
                f"Close the file in any editor or application and try again."
            ) from e
        except OSError as e:
            last_err = e
            break

    if last_err:
        raise last_err
    # Last resort: read as binary and decode with replacement
    return abs_path.read_bytes().decode("utf-8", errors="replace")


def write_file(path: str, content: str, root: str = None) -> str:
    """
    Write file contents.
    
    Args:
        path: File path (relative or absolute)
        content: Content to write
        root: Project root directory (defaults to cwd)
        
    Returns:
        Success message
        
    Raises:
        PermissionError: If path tries to escape workspace
    """
    # Security: Resolve to absolute path
    workspace = Path(root).resolve() if root else Path.cwd().resolve()
    p = Path(path)
    abs_path = (workspace / p).resolve() if not p.is_absolute() else p.resolve()

    # Security: Prevent directory traversal
    if not _is_inside(abs_path, workspace):
        raise PermissionError(f"Access denied: '{path}' is outside workspace")

    # Create parent directories if needed
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        abs_path.write_text(content, encoding="utf-8")
    except PermissionError:
        raise PermissionError(
            f"Cannot write '{path}': file is read-only or locked. "
            f"Close any editor/process using it and try again."
        )

    return f"✅ Written {len(content)} bytes to {path}"


def list_files(directory: str = ".", root: str = None) -> str:
    """
    List files in directory (cross-platform).
    """
    workspace = Path(root).resolve() if root else Path.cwd().resolve()
    d = Path(directory)
    abs_path = (workspace / d).resolve() if not d.is_absolute() else d.resolve()

    if not _is_inside(abs_path, workspace):
        raise PermissionError(f"Access denied: '{directory}' is outside workspace")

    if not abs_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not abs_path.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    items = []
    try:
        entries = sorted(abs_path.iterdir())
    except PermissionError:
        return f"🔒 Permission denied reading directory '{directory}'"

    for item in entries:
        try:
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"📄 {item.name} ({size:,} bytes)")
        except OSError:
            items.append(f"⚠️  {item.name} (unreadable)")

    return "\n".join(items) if items else "📭 Empty directory"


def search_files(pattern: str, directory: str = ".", root: str = None) -> str:
    """
    Search for files matching one or more glob patterns.
    Supports semicolon-separated patterns: "*.py;*.js;README*".
    Cross-platform (Windows backslash / POSIX forward-slash).
    """
    workspace = Path(root).resolve() if root else Path.cwd().resolve()
    d = Path(directory)
    abs_path = (workspace / d).resolve() if not d.is_absolute() else d.resolve()

    if not _is_inside(abs_path, workspace):
        raise PermissionError(f"Access denied: '{directory}' is outside workspace")

    if not abs_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Support semicolon-separated patterns (LLM sometimes sends them together)
    patterns = [p.strip() for p in pattern.replace(",", ";").split(";") if p.strip()]

    seen: set = set()
    matches: list = []
    for pat in patterns:
        try:
            for m in sorted(abs_path.rglob(pat)):
                if m not in seen:
                    seen.add(m)
                    matches.append(m)
        except Exception:
            continue

    if not matches:
        return f"No files matching '{pattern}'"

    results = []
    for match in sorted(matches):
        try:
            rel_path = match.relative_to(workspace)
            # Always use forward slashes in output for cross-platform consistency
            rel_str = rel_path.as_posix()
            if match.is_dir():
                results.append(f"📁 {rel_str}/")
            else:
                results.append(f"📄 {rel_str}")
        except (ValueError, OSError):
            results.append(f"📄 {match.name}")

    return "\n".join(results)


def get_cwd() -> str:
    """
    Get current working directory.
    
    Returns:
        Current working directory path
    """
    return str(Path.cwd())
