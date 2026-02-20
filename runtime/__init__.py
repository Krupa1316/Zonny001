"""
Runtime - Pure Python Agent Execution Engine

A clean, decoupled runtime kernel for agent-based systems.

Key components:
- base: Interface contracts (BaseAgent, BaseTool)
- context: Execution state container
- registry: Dynamic agent/tool registration
- engine: Orchestration loop

Usage:
    from runtime import ExecutionEngine, AgentRegistry
    
    registry = AgentRegistry()
    engine = ExecutionEngine(planner, registry)
    result = engine.run("build login system")
"""

from runtime.base import BaseAgent, BaseTool
from runtime.context import AgentContext
from runtime.registry import AgentRegistry
from runtime.engine import ExecutionEngine

__all__ = [
    'BaseAgent',
    'BaseTool',
    'AgentContext',
    'AgentRegistry',
    'ExecutionEngine',
]
