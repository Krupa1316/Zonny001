"""
Slice D - Shell Tools

Tools for shell command execution.

⚠️ SECURITY WARNING:
- Limited command whitelist
- No sudo/rm/destructive commands
- Output truncated
- Timeout enforced

Tools:
- run_shell: Execute safe shell command
"""

import subprocess
import shlex
from pathlib import Path


# Security: Only these commands are allowed
ALLOWED_COMMANDS = {
    "ls", "dir", "pwd", "echo", "cat", "head", "tail",
    "grep", "find", "git", "python", "pip", "node", "npm",
}

# Security: These commands are NEVER allowed
BLOCKED_COMMANDS = {
    "rm", "sudo", "su", "chmod", "chown", "mv", "dd",
    "mkfs", "format", "del", "rmdir", "kill", "killall",
}


def run_shell(command: str, timeout: int = 10) -> str:
    """
    Execute shell command with security restrictions.
    
    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default: 10)
        
    Returns:
        Command output
        
    Raises:
        PermissionError: If command is not allowed
        TimeoutError: If command times out
        
    Security:
    - Whitelist-based command filtering
    - Blocked dangerous commands
    - Output truncation (max 10KB)
    - Timeout enforcement
    - Workspace-scoped execution
    """
    # Security: Parse command
    parts = shlex.split(command)
    
    if not parts:
        raise ValueError("Empty command")
    
    base_cmd = parts[0].lower()
    
    # Security: Check if command is blocked
    if base_cmd in BLOCKED_COMMANDS:
        raise PermissionError(f"Blocked command: {base_cmd}")
    
    # Security: Check if command is allowed
    if base_cmd not in ALLOWED_COMMANDS:
        raise PermissionError(f"Command not in allowed list: {base_cmd}")
    
    # Execute in workspace
    workspace = Path.cwd()
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(workspace)
        )
        
        output = result.stdout + result.stderr
        
        # Security: Truncate output
        max_output = 10 * 1024  # 10KB
        if len(output) > max_output:
            output = output[:max_output] + "\n\n⚠️ Output truncated (max 10KB)"
        
        if result.returncode != 0:
            return f"❌ Command failed (exit code {result.returncode}):\n{output}"
        
        return output if output else "✅ Command completed (no output)"
        
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout}s")
    except Exception as e:
        return f"❌ Error executing command: {e}"
