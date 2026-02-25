"""
️ Execution Context

Holds EVERYTHING about a task execution.

No LLM logic here. Just state.
"""

import uuid
from datetime import datetime


class AgentContext:
    """
    Container for all execution state.
    
    This tracks:
    - User input
    - Execution plan
    - Tool outputs
    - Memory
    - Final result
    
    Clean separation: context = data, engine = logic.
    """
    
    def __init__(self, user_input):
        # Identity
        self.run_id = str(uuid.uuid4())
        self.created_at = datetime.now()
        
        # Input
        self.user_input = user_input
        
        # Planning
        self.plan = []
        self.current_step = 0
        
        # State
        self.memory = {}
        self.tool_outputs = {}
        self.errors = []
        
        # Output
        self.final_answer = None
        self.completed = False
    
    def add_tool_output(self, name, output):
        """Store output from a tool/agent execution"""
        self.tool_outputs[name] = output
    
    def add_error(self, error):
        """Track errors during execution"""
        self.errors.append(str(error))
    
    def set_memory(self, key, value):
        """Store arbitrary data in context memory"""
        self.memory[key] = value
    
    def get_memory(self, key, default=None):
        """Retrieve data from context memory"""
        return self.memory.get(key, default)
    
    def mark_complete(self, final_answer):
        """Mark execution as complete with final result"""
        self.final_answer = final_answer
        self.completed = True
    
    def to_dict(self):
        """Serialize context for logging/debugging"""
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "user_input": self.user_input,
            "plan": self.plan,
            "current_step": self.current_step,
            "tool_outputs": self.tool_outputs,
            "completed": self.completed,
            "errors": self.errors
        }
