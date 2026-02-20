"""
Zonny Router - Request Handler

This is where decisions are made.

The router:
- Receives requests from MCP Gateway
- Decides what to do (command vs input)
- Routes to appropriate handler
- Returns response

This is the ONLY place that knows about:
- Agents
- Memory
- Tools
- Planner
"""

from typing import Optional, Dict, Any
from runtime.registry import AgentRegistry


class ZonnyRouter:
    """
    Request router for Zonny system.
    
    Handles all routing logic that CLI and Gateway don't know about.
    """
    
    def __init__(self, registry: AgentRegistry):
        """
        Initialize router.
        
        Args:
            registry: AgentRegistry instance
        """
        self.registry = registry
    
    def dispatch(self, input_text: Optional[str], command: Optional[str], context: Dict[str, Any]) -> str:
        """
        Main dispatch method.
        
        Args:
            input_text: User input (if chat)
            command: Command (if starts with /)
            context: Request context (session, cwd, etc.)
            
        Returns:
            Response string to send back to CLI
        """
        # Route commands
        if command:
            return self._handle_command(command, context)
        
        # Route input
        if input_text:
            return self._handle_input(input_text, context)
        
        return "❌ No input or command provided"
    
    def _handle_command(self, command: str, context: Dict[str, Any]) -> str:
        """
        Handle commands (start with /).
        
        Args:
            command: Command string (e.g. "/agents")
            context: Request context
            
        Returns:
            Command response
        """
        cmd = command.lower().strip()
        
        if cmd == "/agents":
            return self._cmd_agents()
        
        elif cmd == "/help":
            return self._cmd_help()
        
        elif cmd == "/status":
            return self._cmd_status(context)
        
        else:
            return f"❌ Unknown command: {command}\n\n💡 Try /help for available commands"
    
    def _handle_input(self, input_text: str, context: Dict[str, Any]) -> str:
        """
        Handle user input (chat).
        
        For Slice A, this is just an echo.
        Later phases will add:
        - Planner
        - Agent execution
        - Memory
        
        Args:
            input_text: User's message
            context: Request context
            
        Returns:
            Response text
        """
        session = context.get("session", "unknown")[:8]
        
        # For Slice A: Echo + basic info
        response = f"""📝 Received your input (Slice A - Echo Mode)

Your message: {input_text}
Session: {session}...

🔜 In future slices:
   • Planner will analyze this
   • Agents will be selected
   • Tools will execute
   • Memory will be stored

For now, Slice A infrastructure is working! ✅"""
        
        return response
    
    def _cmd_agents(self) -> str:
        """
        Handle /agents command - list all agents.
        
        Returns:
            Formatted agent list
        """
        agents = self.registry.list_agents()
        
        if not agents:
            return "No agents registered"
        
        output = "📋 Available Agents\n"
        output += "="*70 + "\n\n"
        
        for agent in agents:
            status = "✅ ENABLED " if agent['enabled'] else "❌ DISABLED"
            output += f"{status} | {agent['name']}\n"
            output += f"           Description: {agent['description']}\n"
            output += f"           Priority: {agent['priority']} | Tools: {len(agent['tools'])}\n"
            output += "\n"
        
        output += f"Total: {len(agents)} agents"
        
        return output
    
    def _cmd_help(self) -> str:
        """
        Handle /help command.
        
        Returns:
            Help text
        """
        return """📖 Zonny Help

Commands:
  /agents     - List all available agents and their status
  /help       - Show this help message
  /status     - Show current session status
  /exit       - Exit Zonny

Chat:
  Just type your message and press Enter to chat with agents.

Architecture:
  Zonny uses a Gemini-style agent system with:
  • Multi-agent orchestration
  • Declarative YAML manifests
  • Independent cognitive loops
  • Tool-based execution

Current Phase: Slice A (Interface Layer)
  ✅ CLI interface
  ✅ MCP Gateway
  ✅ Request routing

Next Phases:
  🔜 Agent execution
  🔜 Memory integration
  🔜 Tool calling"""
    
    def _cmd_status(self, context: Dict[str, Any]) -> str:
        """
        Handle /status command - show session info.
        
        Args:
            context: Request context
            
        Returns:
            Status information
        """
        session = context.get("session", "unknown")
        cwd = context.get("cwd", "unknown")
        
        agents = self.registry.list_agents()
        enabled_count = sum(1 for a in agents if a['enabled'])
        
        output = "📊 Zonny Status\n"
        output += "="*70 + "\n\n"
        output += f"Session ID: {session}\n"
        output += f"Working Dir: {cwd}\n"
        output += f"Agents: {enabled_count}/{len(agents)} enabled\n"
        output += f"Phase: Slice A (Interface Layer)\n"
        
        return output
