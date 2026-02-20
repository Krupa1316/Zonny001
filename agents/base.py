"""
Slice B - Agent Interface Contract

Every agent in Zonny must subclass this.

This guarantees:
• Uniform interface
• Interchangeable agents
• Dynamic registry
• Predictable execution

Design Philosophy:
- All agents look the same from the outside
- Input → Agent → Output
- Context dict for extensibility
- Simple, production-ready
"""


class Agent:
    """
    Base Agent Interface
    
    All agents must implement:
    - name: unique identifier
    - description: what this agent does
    - run(input, context): execute and return output
    """
    
    name = "base"
    description = "Base agent interface"
    
    def run(self, input: str, context: dict) -> str:
        """
        Execute agent logic.
        
        Args:
            input: User input or task description
            context: Execution context (session, cwd, etc.)
            
        Returns:
            String output to return to user
        """
        raise NotImplementedError(f"Agent '{self.name}' must implement run()")
