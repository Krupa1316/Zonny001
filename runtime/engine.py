"""
🚀 Execution Engine

The heart of the runtime.

Orchestrates everything:
- Creates context
- Asks planner
- Executes steps
- Tracks state
- Returns result

NO agent logic here.
NO tool implementations here.
ONLY control flow.

This is the kernel.
"""

from runtime.context import AgentContext
from runtime.subagent import SubAgentRunner


class ExecutionEngine:
    """
    Core execution loop.
    
    Engine NEVER:
    ❌ talks to Ollama
    ❌ accesses filesystem
    ❌ queries Chroma
    
    Only agents do that.
    Engine orchestrates only.
    
    This keeps architecture clean.
    """
    
    def __init__(self, planner_agent, registry):
        """
        Initialize engine.
        
        Args:
            planner_agent: Agent that creates execution plans
            registry: AgentRegistry with available agents/tools
        """
        self.planner = planner_agent
        self.registry = registry
    
    def run(self, user_input, verbose=False):
        """
        Execute a user request.
        
        Flow:
        1. Create context
        2. Ask planner for plan
        3. Execute each step
        4. Return final result
        
        Args:
            user_input: str, what the user wants
            verbose: bool, print execution details
            
        Returns:
            AgentContext with final result
        """
        # Step 1: Create execution context
        context = AgentContext(user_input)
        
        if verbose:
            print(f"\n🎯 Run ID: {context.run_id}")
            print(f"📝 Input: {user_input}\n")
        
        try:
            # Step 2: Ask planner what to do
            if verbose:
                print("🧠 Asking planner...")
            
            plan = self.planner.execute(context, user_input)
            context.plan = plan
            
            if verbose:
                print(f"📋 Plan created: {len(plan)} steps\n")
            
            # Step 3: Execute each step
            for i, step in enumerate(plan):
                context.current_step = i
                
                # Check if this is a subagent (Phase 3.2) or regular agent
                if "subagent" in step:
                    # SubAgent with cognitive loop
                    subagent_name = step.get("subagent")
                    
                    # Phase 4: Check if agent is enabled
                    if not self.registry.is_agent_enabled(subagent_name):
                        error_msg = f"Agent '{subagent_name}' is disabled"
                        if verbose:
                            print(f"⚙️  Step {i+1}/{len(plan)}: ⛔ {error_msg}")
                        raise Exception(error_msg)
                    
                    if verbose:
                        print(f"⚙️  Step {i+1}/{len(plan)}: 🤖 SubAgent '{subagent_name}'")
                    
                    # Get manifest
                    manifest = self.registry.get_manifest(subagent_name)
                    if not manifest:
                        raise Exception(f"Manifest not found: {subagent_name}")
                    
                    # Create SubAgentRunner
                    runner = SubAgentRunner(manifest, self.registry.tools)
                    
                    # Run subagent
                    result = runner.run(context.user_input)
                    context.add_tool_output(subagent_name, result)
                    
                    if verbose:
                        print(f"   ✅ SubAgent completed\n")
                
                elif "agent" in step:
                    # Regular agent (Phase 1 style)
                    agent_name = step.get("agent")
                    
                    if verbose:
                        print(f"⚙️  Step {i+1}/{len(plan)}: {agent_name}")
                    
                    # Get agent from registry
                    agent = self.registry.get_agent(agent_name)
                    if not agent:
                        raise Exception(f"Agent not found: {agent_name}")
                    
                    # Execute agent
                    result = agent.execute(context, step)
                    context.add_tool_output(agent_name, result)
                    
                    if verbose:
                        print(f"   ✅ Result: {str(result)[:100]}...\n")
                
                else:
                    raise Exception(f"Step {i} must have 'agent' or 'subagent' key")
            
            # Step 4: Mark complete
            # By default, final answer is all tool outputs
            # Planner or final agent can override this
            if context.final_answer is None:
                context.mark_complete(context.tool_outputs)
            
            if verbose:
                print("✅ Execution complete!\n")
            
        except Exception as e:
            context.add_error(e)
            if verbose:
                print(f"❌ Error: {e}\n")
            raise
        
        return context
    
    def run_async(self, user_input):
        """
        Async version of run() for future use.
        
        Currently just calls run(), but structure allows
        async agent implementations later.
        """
        # TODO: Implement async execution
        return self.run(user_input)
