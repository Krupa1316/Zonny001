"""
Zonny Executor - Phase 2 Architecture

Executes multi-step plans produced by Planner.

This is the execution engine that:
- Runs plan steps sequentially
- Calls dispatcher for each tool
- Collects results
- Handles errors gracefully

Executor ONLY executes - it doesn't plan or reflect.
"""

from zonny.dispatcher import dispatch


def execute_plan(plan: dict, context: dict, verbose: bool = True) -> dict:
    """
    Execute a plan step-by-step.
    
    Args:
        plan: Plan dict from planner {"goal": "...", "steps": [...]}
        context: Execution context (session, workspace, etc.)
        verbose: Print step-by-step progress
        
    Returns:
        Execution result: {
            "goal": "...",
            "steps_completed": N,
            "results": [...],
            "success": True/False,
            "error": None or error message
        }
    """
    goal = plan.get("goal", "Unknown goal")
    steps = plan.get("steps", [])
    
    if not steps:
        return {
            "goal": goal,
            "steps_completed": 0,
            "results": [],
            "success": False,
            "error": "No steps in plan"
        }
    
    results = []
    step_num = 0
    
    try:
        for step_num, step in enumerate(steps, 1):
            task = step.get("task", "Unknown task")
            tool = step.get("tool")
            args = step.get("args", {})
            
            if verbose:
                print(f"→ Step {step_num}/{len(steps)}: {task}")
            
            # Create intent for dispatcher
            intent = {
                "tool": tool,
                "args": args
            }
            
            # Execute via dispatcher
            result = dispatch(intent, context)
            
            # Store result
            step_result = {
                "step": step_num,
                "task": task,
                "tool": tool,
                "result": result,
                "success": not result.startswith("[FAIL]") if isinstance(result, str) else True
            }
            
            results.append(step_result)
            
            # If step failed, decide whether to continue
            if not step_result["success"]:
                if verbose:
                    print(f" [WARN]️ Step {step_num} had errors, continuing...")
        
        # All steps completed
        return {
            "goal": goal,
            "steps_completed": step_num,
            "total_steps": len(steps),
            "results": results,
            "success": True,
            "error": None
        }
        
    except Exception as e:
        # Execution error
        return {
            "goal": goal,
            "steps_completed": step_num,
            "total_steps": len(steps),
            "results": results,
            "success": False,
            "error": f"Execution error at step {step_num}: {e}"
        }


def format_execution_summary(execution: dict) -> str:
    """
    Format execution results into human-readable summary.
    
    Args:
        execution: Result from execute_plan()
        
    Returns:
        Formatted string summary
    """
    lines = []
    
    lines.append(f"[TARGET] Goal: {execution['goal']}")
    lines.append(f" Completed: {execution['steps_completed']}/{execution['total_steps']} steps")
    
    if execution.get("error"):
        lines.append(f"[FAIL] Error: {execution['error']}")
    
    lines.append("")
    lines.append("Results:")
    
    for step_result in execution["results"]:
        step_num = step_result["step"]
        task = step_result["task"]
        success = step_result["success"]
        result = step_result["result"]
        
        status = "" if success else "[WARN]️"
        lines.append(f"{status} Step {step_num}: {task}")
        
        # Show result preview (first 200 chars)
        if isinstance(result, str):
            preview = result[:200] + "..." if len(result) > 200 else result
            lines.append(f" {preview}")
        
        lines.append("")
    
    return "\n".join(lines)


def get_final_result(execution: dict) -> str:
    """
    Get the final result from execution (typically last step's output).
    
    Args:
        execution: Result from execute_plan()
        
    Returns:
        String result to show user
    """
    if not execution.get("results"):
        return execution.get("error", "No results")
    
    # Get last successful result
    for step_result in reversed(execution["results"]):
        if step_result.get("success") and step_result.get("result"):
            return step_result["result"]
    
    # If no successful results, return error
    return execution.get("error", "No successful results")


# ============================================
# PHASE 6: ReAct Architecture - Single Action Executor
# ============================================


class SingleActionExecutor:
    """
    Phase 6 Executor - Runs ONE action at a time.
    
    Used by ReAct loop for reactive execution.
    Each action returns an observation that informs the next decision.
    """
    
    def __init__(self, project_root: str = "."):
        """Initialize executor with working directory."""
        self.project_root = project_root
        self.context = {"project_root": project_root}
    
    def run_single(self, action: str, args: dict) -> any:
        """
        Execute a single action and return result.
        
        Args:
            action: Tool name (e.g., "filesystem.list")
            args: Tool arguments
            
        Returns:
            Raw result from tool execution
            
        Raises:
            Exception if action fails
        """
        # Create intent for dispatcher
        intent = {
            "tool": action,
            "args": args
        }
        
        # Execute via dispatcher
        result = dispatch(intent, self.context)
        
        return result
