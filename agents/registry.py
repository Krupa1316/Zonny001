"""
Slice B - Agent Registry

Dynamic agent registration and lookup.

This enables:
• Hot-loading agents
• Runtime discovery
• Loose coupling
• Extensibility

Design:
- Simple dict-based registry
- Register agents at import time
- Get agent by name
- List all available agents
"""


# Global registry
AGENTS = {}


def register(agent):
    """
    Register an agent instance.
    
    Args:
        agent: Agent instance (must have .name attribute)
    """
    if not hasattr(agent, 'name'):
        raise ValueError("Agent must have 'name' attribute")
    
    AGENTS[agent.name] = agent
    print(f"🔌 Registered agent: {agent.name}")


def get(name: str):
    """
    Get agent by name.
    
    Args:
        name: Agent name
        
    Returns:
        Agent instance or None
    """
    return AGENTS.get(name)


def list_agents():
    """
    List all registered agent names.
    
    Returns:
        List of agent names
    """
    return list(AGENTS.keys())


def get_all():
    """
    Get all registered agents.
    
    Returns:
        Dict of {name: agent}
    """
    return AGENTS.copy()
