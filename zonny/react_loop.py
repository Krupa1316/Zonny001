"""
ReAct Loop - The Heart of Zonny

This is the fundamental loop that powers all modern AI agents:
- Gemini CLI
- Claude Code 
- OpenAI Agents

Architecture:
    Think → Act → Observe → Think → Act → Observe → ... → Answer

No static plans. No assumptions. Just reactive intelligence.
"""

import sys
from typing import Optional
from zonny.world import WorldState, Decision, create_initial_world


class ReActLoop:
    """
    The core reasoning loop.
    
    This replaces the old Plan-Execute-Reflect architecture with
    adaptive, reactive decision-making.
    """
    
    def __init__(self, planner, executor, max_iterations: int = 50, verbose: bool = True):
        """
        Initialize ReAct loop.
        
        Args:
            planner: Decision engine (makes ONE decision at a time)
            executor: Action executor (runs single actions)
            max_iterations: Safety limit to prevent infinite loops
            verbose: Print thinking process
        """
        self.planner = planner
        self.executor = executor
        self.max_iterations = max_iterations
        self.verbose = verbose
    
    def run(self, user_query: str, project_root: str = ".") -> str:
        """
        Execute the ReAct loop.
        
        This is the main entry point - it replaces everything from the old system.
        
        Args:
            user_query: User's request
            project_root: Working directory
            
        Returns:
            Final answer string
        """
        # Initialize world state
        world = create_initial_world(user_query, project_root)
        
        if self.verbose:
            print(f"{'─'*70}")
            print(f" Starting exploration...")
            print(f"{'─'*70}\n")
        
        # Main loop - this is Zonny's cognition
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            # THINK: Make ONE decision based on current world state
            try:
                decision = self.planner.decide(world)
            except Exception as e:
                if self.verbose:
                    print(f"[FAIL] Planner error: {e}")
                world.update(
                    observation=f"Planner failed: {str(e)}",
                    error=str(e)
                )
                # Try to recover with simple answer
                return self._create_error_response(world, str(e))
            
            # Display thinking (like Gemini format)
            if self.verbose:
                print(f" {decision.thought}")
            
            # CHECK: Are we done?
            if decision.done:
                if self.verbose:
                    print(f"\n{'─'*70}")
                    print(f" Analysis complete after {iteration} iterations")
                    print(f"{'─'*70}\n")
                
                return decision.final_answer or "Task completed but no answer provided."
            
            # ACT: Execute the single action
            if self.verbose:
                action_display = decision.action.replace("filesystem.", "").replace("workspace.", "")
                args_display = decision.args.get('path', '') if 'path' in decision.args else str(decision.args)
                print(f" {action_display.title()} {args_display}")
            
            try:
                result = self.executor.run_single(decision.action, decision.args)
                
                # OBSERVE: Update world state with result
                observation = self._format_observation(decision.action, result)
                world.update(
                    observation=observation,
                    result=result
                )
                
                # Store file contents in knowledge for later summarization
                if decision.action == "filesystem.read" and isinstance(result, str):
                    file_path = decision.args.get('path', 'unknown')
                    if 'file_contents' not in world.knowledge:
                        world.knowledge['file_contents'] = {}
                    # Strip the dispatcher prefix ("[DOC] Contents of path:\n\n") before storing
                    raw = result
                    if result.startswith("[DOC] Contents of"):
                        sep = result.find("\n\n")
                        if sep != -1:
                            raw = result[sep + 2:]
                    world.knowledge['file_contents'][file_path] = raw[:3000]
                
                # Track action
                world.action_history.append({
                    "action": decision.action,
                    "args": decision.args,
                    "iteration": iteration
                })
                world.last_action = {"action": decision.action, "args": decision.args}
                
                # Update files list if this was a list action
                if decision.action == "filesystem.list" and isinstance(result, list):
                    world.files = result
                
                # Show brief result summary (like Gemini)
                if self.verbose:
                    if isinstance(result, str) and len(result) > 100:
                        line_count = result.count('\n') + 1
                        print(f" → Read {len(result)} chars ({line_count} lines)")
                    elif isinstance(result, list):
                        print(f" → Found {len(result)} items")
                    print() # Blank line for readability
                
            except Exception as e:
                error_msg = f"Action '{decision.action}' failed: {str(e)}"
                if self.verbose:
                    print(f" \u274c {error_msg}\n")
                
                world.update(
                    observation=error_msg,
                    error=error_msg
                )
                
                # Agent will see the error and can adapt
                # This is self-correction in action
        
        # Safety: Hit max iterations
        if self.verbose:
            print(f"\n{'─'*70}")
            print(f"[WARN]️ Reached maximum iterations ({self.max_iterations})")
            print(f"{'─'*70}\n")
        
        return self._create_timeout_response(world)
    
    def _format_observation(self, action: str, result) -> str:
        """
        Convert raw result into human-readable observation.
        Always returns enough content for the LLM to reason about.
        """
        if result is None:
            return f"Action '{action}' completed with no output"

        if isinstance(result, list):
            if action == "filesystem.list":
                listing = "\n".join(str(i) for i in result[:50])
                return f"Directory listing ({len(result)} items):\n{listing}"
            return f"Action returned list with {len(result)} items"

        if isinstance(result, str):
            # ── Filesystem listing: return full content so LLM sees actual files ──
            if action in ("filesystem.list", "workspace.tree", "workspace.scan"):
                return result[:3000] + ("\n... (truncated)" if len(result) > 3000 else "")

            # ── File reads: return actual file content (strip dispatcher prefix) ──
            if action == "filesystem.read":
                content = result
                # Strip the "[DOC] Contents of path:\n\n" prefix added by dispatcher
                if result.startswith("[DOC] Contents of"):
                    sep = result.find("\n\n")
                    if sep != -1:
                        content = result[sep + 2:]
                return content[:4000] + ("\n... (truncated)" if len(content) > 4000 else "")

            # ── Search results: return full list ──
            if action == "filesystem.search":
                return result[:2000] + ("\n... (truncated)" if len(result) > 2000 else "")

            # ── Other string results ──
            length = len(result)
            if length > 500:
                return result[:500] + f"\n... ({length} chars total)"
            return result

        if isinstance(result, dict):
            import json as _json
            try:
                return _json.dumps(result, indent=2)[:1000]
            except Exception:
                return f"Action returned data with keys: {list(result.keys())}"

        return f"Action completed successfully"
    
    def _create_error_response(self, world: WorldState, error: str) -> str:
        """Create response when planner fails."""
        return f"""I encountered an error while planning: {error}

Based on what I observed so far:
{chr(10).join(f'- {obs}' for obs in world.observations[-3:])}

I wasn't able to complete the task. Please try rephrasing your request."""
    
    def _create_timeout_response(self, world: WorldState) -> str:
        """Create response when hitting max iterations."""
        return f"""I reached the maximum number of decision cycles ({self.max_iterations}).

What I learned:
{chr(10).join(f'- {obs}' for obs in world.observations[-5:])}

The task may be too complex or I may be stuck. Please try a more specific request."""


def run_react_agent(user_query: str, project_root: str = ".", 
                    max_iterations: int = 15, verbose: bool = True) -> str:
    """
    Convenience function to run ReAct loop with all components.
    
    This initializes planner and executor and runs the loop.
    
    Args:
        user_query: User's request
        project_root: Working directory
        max_iterations: Safety limit
        verbose: Show thinking process
        
    Returns:
        Final answer
    """
    # Import here to avoid circular dependencies
    from zonny.planner import ReactPlanner
    from zonny.executor import SingleActionExecutor
    
    planner = ReactPlanner()
    executor = SingleActionExecutor(project_root=project_root)
    
    loop = ReActLoop(planner, executor, max_iterations, verbose)
    return loop.run(user_query, project_root)
