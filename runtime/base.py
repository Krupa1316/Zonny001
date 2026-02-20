"""
🔧 Base Interfaces

Core contracts for agents and tools.
Everything must conform to these interfaces.

This is your type system.
"""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    Base interface for all agents.
    
    Agents perform tasks using context and potentially calling tools.
    They must implement execute() method.
    """
    name = "base"
    
    @abstractmethod
    def execute(self, context, task):
        """
        Execute agent logic.
        
        Args:
            context: AgentContext with run state
            task: dict with task details
            
        Returns:
            Result of agent execution
        """
        pass


class BaseTool(ABC):
    """
    Base interface for all tools.
    
    Tools are atomic operations (read file, call API, query DB, etc.).
    They must implement execute() method.
    """
    name = "tool"
    
    @abstractmethod
    def execute(self, input):
        """
        Execute tool logic.
        
        Args:
            input: Tool-specific input
            
        Returns:
            Tool output
        """
        pass
