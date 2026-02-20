"""
Agents package

Slice B: Agent Core
- Base interface (all agents subclass Agent)
- Registry (dynamic registration)
- Router (decider agent)
- Concrete agents (general, docs, code, memory)

Phase 2 (legacy):
- PlannerAgent (still available)
"""

# Slice B - Import and register agents
from .registry import register

# Initialize silently (avoid emoji encoding issues on Windows)
# print("\n🚀 Initializing Slice B Agent System...")

# Import ALL agents (no optional imports)
from .router import RouterAgent
from .general import GeneralAgent
from .docs import DocsAgent
from .code import CodeAgent
from .memory import MemoryAgent

# Register all agents
register(RouterAgent())
register(GeneralAgent())
register(DocsAgent())
register(CodeAgent())
register(MemoryAgent())

# print("✅ Slice B Agent System Ready\n")

# Phase 2 (legacy)
from .planner_agent import PlannerAgent

__all__ = [
    'PlannerAgent',  # Phase 2
    'RouterAgent',   # Slice B
    'GeneralAgent',  # Slice B
    'DocsAgent',     # Slice B
    'CodeAgent',     # Slice B
    'MemoryAgent',   # Slice B
]
