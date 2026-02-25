"""
WorldState - Agent's Mental Model

The agent's understanding of reality that grows with each observation.

This is the foundation of ReAct architecture:
- Agent sees world state
- Makes ONE decision
- Updates world state with observation
- Repeats until done
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class WorldState:
    """
    The agent's complete understanding at any moment.
    
    This grows incrementally as the agent takes actions and observes results.
    No assumptions about the future - only what has been observed.
    """
    
    # Original request
    user_query: str
    
    # What the agent has learned
    observations: List[str] = field(default_factory=list)
    
    # Files discovered (if any)
    files: List[Dict[str, Any]] = field(default_factory=list)
    
    # Last action taken
    last_action: Optional[Dict[str, Any]] = None
    
    # Errors encountered
    errors: List[str] = field(default_factory=list)
    
    # History of all actions
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Accumulated knowledge
    knowledge: Dict[str, Any] = field(default_factory=dict)
    
    # Iteration count
    iteration: int = 0
    
    def update(self, observation: str, result: Any = None, error: str = None):
        """
        Update world state after an action.
        
        Args:
            observation: Human-readable description of what happened
            result: Raw result data from the action
            error: Error message if action failed
        """
        self.observations.append(observation)
        
        if error:
            self.errors.append(error)
            
        if result:
            # Store result in knowledge base
            if self.last_action:
                action_name = self.last_action.get('action', 'unknown')
                self.knowledge[f"result_{self.iteration}_{action_name}"] = result
                
        self.iteration += 1
    
    def get_context_summary(self) -> str:
        """
        Format world state for LLM consumption.
        
        Returns human-readable summary of everything the agent knows.
        """
        parts = [f"User Request: {self.user_query}\n"]
        
        if self.files:
            parts.append(f"Known Files ({len(self.files)}):")
            for f in self.files[:10]: # Limit to 10 for brevity
                if isinstance(f, dict):
                    name = f.get('name', str(f))
                    size = f.get('size', '')
                    size_str = f" ({size} bytes)" if size else ""
                    parts.append(f" - {name}{size_str}")
                else:
                    parts.append(f" - {f}")
            if len(self.files) > 10:
                parts.append(f" ... and {len(self.files) - 10} more")
            parts.append("")
        
        if self.observations:
            parts.append("Observations So Far:")
            for i, obs in enumerate(self.observations[-5:], 1): # Last 5
                parts.append(f" {i}. {obs}")
            if len(self.observations) > 5:
                parts.append(f" ... ({len(self.observations) - 5} earlier observations)")
            parts.append("")
        
        if self.errors:
            parts.append("Errors Encountered:")
            for err in self.errors:
                parts.append(f" [WARN]️ {err}")
            parts.append("")
        
        if self.action_history:
            parts.append("Actions Taken:")
            for action in self.action_history[-3:]: # Last 3
                parts.append(f" → {action.get('action', 'unknown')} {action.get('args', {})}")
            parts.append("")
        
        # Include actual file contents so LLM can summarize them
        file_contents = self.knowledge.get('file_contents', {})
        if file_contents:
            parts.append(f"File Contents Read ({len(file_contents)} files):")
            for file_path, content in file_contents.items():
                parts.append(f"\n--- {file_path} ---")
                # Include up to 1500 chars per file to keep prompt manageable
                parts.append(content[:1500])
                if len(content) > 1500:
                    parts.append(f"... [truncated, {len(content)} chars total]")
            parts.append("")
        
        parts.append(f"Iteration: {self.iteration}")
        
        return "\n".join(parts)


@dataclass
class Decision:
    """
    A single decision made by the planner.
    
    In ReAct architecture, the planner makes ONE decision at a time,
    then observes the result before making the next decision.
    
    This is fundamentally different from static planning.
    """
    
    # What the agent is thinking
    thought: str
    
    # Action to take (None if done)
    action: Optional[str] = None
    
    # Arguments for the action
    args: Dict[str, Any] = field(default_factory=dict)
    
    # Is the task complete?
    done: bool = False
    
    # Final answer (only if done=True)
    final_answer: Optional[str] = None
    
    # Confidence (0.0 to 1.0)
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "thought": self.thought,
            "action": self.action,
            "args": self.args,
            "done": self.done,
            "final_answer": self.final_answer,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Decision':
        """Create Decision from dictionary."""
        return cls(
            thought=data.get("thought", ""),
            action=data.get("action"),
            args=data.get("args", {}),
            done=data.get("done", False),
            final_answer=data.get("final_answer"),
            confidence=data.get("confidence", 1.0)
        )
    
    def __repr__(self) -> str:
        if self.done:
            return f"Decision(done=True, answer={self.final_answer[:50]}...)"
        return f"Decision(action={self.action}, args={self.args})"


def create_initial_world(user_query: str, project_root: str = ".") -> WorldState:
    """
    Create initial world state for a user query.
    """
    from pathlib import Path
    world = WorldState(user_query=user_query)
    abs_root = str(Path(project_root).resolve())
    world.knowledge['project_root'] = project_root
    world.knowledge['abs_root'] = abs_root
    folder_name = Path(abs_root).name
    world.observations.append(
        f"Working in directory: {abs_root}\n"
        f"PATH RULE: All file paths are relative to the workspace root (.). "
        f"Use 'package.json', NOT '{folder_name}/package.json'. "
        f"NEVER prepend the workspace folder name to any path."
    )
    return world
