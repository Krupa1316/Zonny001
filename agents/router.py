"""
Slice B - Router Agent (Decider)

This agent NEVER replies to users.

It only decides: Which agent should handle this?

Critical Design Rule:
- Router NEVER answers
- Router only dispatches
- If router answers, architecture collapses

Current Implementation:
- Deterministic keyword matching
- Later replaced by LLM planner

Routing Logic:
- "pdf" or "document" → docs agent
- "code" → code agent
- default → general agent
"""

from agents.base import Agent


class RouterAgent(Agent):
    """
    Router Agent - Decides which agent handles input.
    
    This is the decider/orchestrator.
    NEVER returns user-facing output.
    Only returns routing decisions.
    """
    
    name = "router"
    description = "Decides which agent should handle user input"
    
    def run(self, input: str, context: dict) -> dict:
        """
        Analyze input and decide which agent to use.
        
        Args:
            input: User input
            context: Execution context
            
        Returns:
            Dict with "agent" key containing target agent name
            
        Note:
            Returns dict, NOT string. This is intentional.
            Router never returns user-facing text.
        """
        if not input:
            return {"agent": "general"}
        
        text = input.lower()
        
        # Slice D: Route file operations to code agent
        if any(word in text for word in ["open", "read", "show", "file", "list", "search", "find", ".py", ".js", ".json", "directory", "folder"]):
            # But not if clearly about documents/PDFs
            if "pdf" not in text and "document" not in text:
                return {"agent": "code"}
        
        # Document/PDF routing
        if "pdf" in text or "document" in text:
            return {"agent": "docs"}
        
        # Code routing (specific code keywords)
        if "code" in text or "function" in text or "class" in text:
            return {"agent": "code"}
        
        # Memory routing
        if "remember" in text or "recall" in text or "history" in text:
            return {"agent": "memory"}
        
        # Default to general agent
        return {"agent": "general"}
