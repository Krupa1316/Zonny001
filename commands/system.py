"""
Slice E - System Commands

Handles commands that control Zonny itself (not user tasks).
Commands are executed BEFORE router dispatch.
"""

import json
from typing import Dict, Optional
from agents.registry import list_agents, get as get_agent
from tools.registry import list_tools, get as get_tool
from tools.workspace import get_workspace_summary, get_file_tree, git_status


def handle_system_command(command: str, session_id: str, context: Dict) -> Optional[Dict]:
    """
    Handle system commands.
    
    Args:
        command: The command string (e.g., "/agents", "/help")
        session_id: Current session ID
        context: Current context dict
        
    Returns:
        Response dict if command handled, None if not a system command
    """
    command = command.strip()
    
    # Not a command
    if not command.startswith('/'):
        return None
    
    cmd_lower = command.lower()
    
    # /help - Show available commands
    if cmd_lower == '/help':
        return {
            "response": """[BOT] Zonny System Commands

[LIST] Information:
  /help - Show this help
  /status - Show system status
  /agents - List available agents
  /tools - List available tools
  /workspace - Show workspace info
  /tree - Show file tree
  /git - Show git status

️ Session Control:
  /new - Start new session
  /clear - Clear conversation (keep session)
  /reset - Full system reset

 Documentation:
  /docs - List loaded documents
  
Type your request normally (no slash) to talk to agents."""
        }
    
    # /status - System status
    elif cmd_lower == '/status':
        agent_list = list_agents()
        tool_list = list_tools()
        
        status = f"""[BOT] Zonny Status
{"="*50}

Session: {session_id[:8]}...
Agents: {len(agent_list)} loaded
Tools: {len(tool_list)} registered
Workspace: {context.get('cwd', 'unknown')}

Active Components:
  • Router: [OK] Ready
  • Memory: [OK] Connected
  • Ollama: [OK] nemotron-3-nano:latest (120s timeout)
"""
        return {"response": status}
    
    # /agents - List agents
    elif cmd_lower == '/agents':
        agent_list = list_agents()
        
        response = "[BOT] Available Agents\n" + "="*50 + "\n\n"
        
        for name in agent_list:
            agent = get_agent(name)
            if agent:
                desc = getattr(agent, 'description', 'No description')
                response += f"• {name}: {desc}\n"
        
        return {"response": response}
    
    # /tools - List tools
    elif cmd_lower == '/tools':
        tool_list = list_tools()
        
        response = "[FIX] Available Tools\n" + "="*50 + "\n\n"
        
        for name in tool_list:
            # Get tool function
            tool_fn = get_tool(name)
            if tool_fn and hasattr(tool_fn, '__doc__'):
                desc = tool_fn.__doc__.strip().split('\n')[0] if tool_fn.__doc__ else 'No description'
                response += f"• {name}: {desc}\n"
            else:
                response += f"• {name}\n"
        
        return {"response": response}
    
    # /workspace - Workspace summary
    elif cmd_lower == '/workspace':
        summary = get_workspace_summary()
        return {"response": summary}
    
    # /tree - File tree
    elif cmd_lower == '/tree':
        tree = get_file_tree(max_depth=3)
        response = "[DIR] File Tree\n" + "="*50 + "\n\n" + tree
        return {"response": response}
    
    # /git - Git status
    elif cmd_lower == '/git':
        git_info = git_status()
        
        if not git_info.get('is_git_repo'):
            return {"response": "[FAIL] Not a git repository"}
        
        response = f""" Git Status
{"="*50}

Branch: {git_info.get('branch', 'unknown')}
Changes: {git_info.get('changes', 0)} files

{git_info.get('status', 'Clean working tree')}
"""
        return {"response": response}
    
    # /docs - List loaded documents
    elif cmd_lower == '/docs':
        docs_info = context.get('loaded_docs', [])
        
        if not docs_info:
            return {"response": " No documents loaded\n\nUse /upload to add documents."}
        
        response = " Loaded Documents\n" + "="*50 + "\n\n"
        for doc in docs_info:
            response += f"• {doc}\n"
        
        return {"response": response}
    
    # /clear - Clear conversation (keep session)
    elif cmd_lower == '/clear':
        return {
            "response": "[DONE] Conversation cleared (session preserved)",
            "action": "clear_conversation"
        }
    
    # /new - Start new session
    elif cmd_lower == '/new':
        return {
            "response": "🆕 Starting new session...",
            "action": "new_session"
        }
    
    # /reset - Full reset
    elif cmd_lower == '/reset':
        return {
            "response": "[REFRESH] System reset complete",
            "action": "reset_system"
        }
    
    # Unknown command
    else:
        return {
            "response": f"[FAIL] Unknown command: {command}\n\nType /help for available commands."
        }
