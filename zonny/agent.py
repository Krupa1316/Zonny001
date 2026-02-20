"""
Zonny Agent - Main Agent Loop

This is the core agent loop that:
1. Takes user input
2. Routes to appropriate mode (ReAct, Planner, or Router)
3. Executes and returns results

PHASE 6: Now supports ReAct architecture (Think → Act → Observe)

All operations are scoped to project_root.
"""

import os
import sys
from zonny.planner import plan, decide_approach
from zonny.executor import execute_plan, get_final_result
from zonny.reflector import reflect
from zonny.semantic_router import route
from zonny.dispatcher import dispatch

# PHASE 6: Enable ReAct mode (set to True to use new architecture)
USE_REACT_MODE = os.environ.get("ZONNY_REACT_MODE", "true").lower() == "true"


def get_directory_snapshot(project_root: str) -> list:
    """
    Get snapshot of files in current directory for context awareness.
    This helps the planner make informed decisions about what exists.
    
    Returns:
        List of dicts: [{"name": "file.py", "size": 1234, "is_dir": False}, ...]"
    """
    try:
        items = []
        for item in os.listdir(project_root):
            item_path = os.path.join(project_root, item)
            is_dir = os.path.isdir(item_path)
            size = 0 if is_dir else os.path.getsize(item_path)
            
            items.append({
                "name": item,
                "size": size,
                "is_dir": is_dir
            })
        
        return items
    except Exception:
        return []


def format_context_for_planner(context: dict) -> str:
    """
    Format context into human-readable string for LLM.
    Helps planner understand what's available before planning.
    """
    lines = []
    
    # Available files
    if context.get("available_files"):
        files = context["available_files"]
        
        # Notable files (analysis, README, setup, etc.)
        notable_files = []
        for f in files:
            if not f["is_dir"]:
                name = f["name"].lower()
                if any(keyword in name for keyword in ["analysis", "readme", "setup", "config", "main", "server"]):
                    notable_files.append(f"{f['name']} ({f['size']} bytes)")
        
        if notable_files:
            lines.append("Notable files available:")
            for nf in notable_files[:5]:  # Top 5
                lines.append(f"  - {nf}")
    
    # Recent operations
    if context.get("recent_operations"):
        recent = context["recent_operations"][-3:]  # Last 3
        lines.append("\nRecent operations:")
        for op in recent:
            lines.append(f"  - {op}")
    
    # Files read in session
    if context.get("files_read"):
        lines.append(f"\nFiles accessed this session: {len(context['files_read'])}")
    
    return "\n".join(lines) if lines else "No additional context."


def loop(project_root: str):
    """
    Main agent loop - runs until user exits.
    
    Args:
        project_root: The directory where Zonny was invoked
    """
    print("💡 Type /exit to quit, or just start chatting!\n")
    
    # Session context with enhanced awareness
    context = {
        "project_root": project_root,
        "files_read": [],
        "commands_run": [],
        "recent_operations": []
    }
    
    # Initialize context with directory scan
    try:
        context["available_files"] = get_directory_snapshot(project_root)
    except Exception:
        context["available_files"] = []
    
    try:
        while True:
            # Get user input
            try:
                user_input = input("➜ Zonny > ").strip()
            except EOFError:
                print("\n👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Handle exit commands
            if user_input.lower() in ['/exit', 'exit', 'quit']:
                print("\n👋 Goodbye!")
                break
            
            # Handle help command
            if user_input.lower() in ['/help', 'help']:
                print_help()
                continue
            
            # Process input
            try:
                result = process_input(user_input, context)
                print(f"\n{result}\n")
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                continue
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
        sys.exit(0)


def process_input(user_input: str, context: dict) -> str:
    """
    Process user input through ReAct, Planner, or Router.
    
    PHASE 6: Supports new ReAct architecture for adaptive intelligence.
    
    Args:
        user_input: What the user typed
        context: Session context including project_root
        
    Returns:
        Result string to display
    """
    # PHASE 6: ReAct Mode - Router selects agent, agent executes via ReAct loop
    if USE_REACT_MODE:
        try:
            from zonny.react_loop import run_react_agent
            from zonny.reflector import reflect as do_reflect

            # Phase 1: Router understands intent and selects agent
            routing = route(user_input, context)

            if routing.get("error") == "ollama_offline":
                return "❌ Ollama is not running. Start it with: ollama serve"

            agent_name = routing.get("agent", "general")
            task = routing.get("task", user_input)
            intent = routing.get("intent", "unknown")
            confidence = routing.get("confidence", 0)

            print(f"🧭 Router → agent: {agent_name}  intent: {intent}  confidence: {confidence:.0%}")
            print(f"📋 Task: {task}")
            print()

            # Phase 2: Agent executes task via ReAct loop
            result = run_react_agent(
                user_query=task,
                project_root=context.get("project_root", "."),
                max_iterations=50,
                verbose=True
            )

            # Phase 4: Reflection — evaluate quality and decide if retry is needed
            try:
                execution_record = {
                    "success": True,
                    "steps_completed": 1,
                    "total_steps": 1,
                    "results": [{"step": 1, "task": task, "tool": "react_loop",
                                 "result": result[:500], "success": True}]
                }
                reflection = do_reflect(user_input, execution_record, context)

                quality = reflection.get("approach_quality", "")
                note = reflection.get("efficiency_note", "")

                # Retry once if reflector says incomplete and provides next action
                if not reflection.get("done") and reflection.get("next_action") and \
                   reflection.get("confidence", 1.0) < 0.6:
                    retry_hint = reflection.get("next_action", "")
                    print(f"\n🔄 Retrying with feedback: {retry_hint}\n")
                    result = run_react_agent(
                        user_query=f"{task}\n\nHint: {retry_hint}",
                        project_root=context.get("project_root", "."),
                        max_iterations=25,
                        verbose=False
                    )
                elif quality in ("excellent", "good") and note:
                    result += f"\n\n✨ {note}"

            except Exception:
                pass  # Reflection is advisory — never block the result

            return result

        except Exception as e:
            print(f"⚠️  ReAct mode failed: {e} — falling back to classic mode")
            # Fall through to classic mode
    
    # CLASSIC MODE: Planner/Router architecture (Phase 1-5)
    
    # Refresh directory snapshot if needed (lightweight operation)
    try:
        context["available_files"] = get_directory_snapshot(context["project_root"])
    except Exception:
        pass
    
    # Let LLM decide approach (no pattern matching)
    decision = decide_approach(user_input, context)
    approach = decision.get("approach", "router")
    
    if approach == "planner":
        # PLANNER MODE: Multi-step workflow
        print(f"🧠 Reasoning: {decision.get('reasoning', 'Multi-step needed')}")
        
        # Add context formatting
        context["context_summary"] = format_context_for_planner(context)
        
        # Create plan with enhanced context
        plan_obj = plan(user_input, context)
        
        if not plan_obj or "error" in plan_obj:
            return f"❌ Planning failed: {plan_obj.get('error', 'Unknown error')}"
        
        print(f"📋 Plan: {plan_obj['goal']}")
        
        # Show reasoning if available
        if plan_obj.get("reasoning"):
            print(f"💡 Strategy: {plan_obj['reasoning']}")
        
        print(f"📝 Steps: {len(plan_obj['steps'])}")
        
        # Track operation
        context["recent_operations"].append(f"Planned: {plan_obj['goal']}")
        context["plan_obj"] = plan_obj  # Pass to reflector
        
        # Execute plan
        execution = execute_plan(plan_obj, context, verbose=True)
        
        # Reflect on execution and approach
        reflection = reflect(plan_obj["goal"], execution, context)
        
        # Get final result
        result = get_final_result(execution)
        
        # Add reflection feedback
        if not reflection.get("done"):
            result += f"\n\n⚠️ Note: {reflection.get('reason', 'Task may be incomplete')}"
        
        # Show approach quality feedback for learning
        approach_quality = reflection.get("approach_quality", "")
        if approach_quality in ["excellent", "good"]:
            efficiency_note = reflection.get("efficiency_note")
            if efficiency_note:
                result += f"\n\n✨ Approach: {approach_quality.capitalize()} - {efficiency_note}"
        elif approach_quality in ["poor", "acceptable"] and reflection.get("efficiency_note"):
            result += f"\n\n💭 Note: {reflection['efficiency_note']}"
        
        return result
    else:
        # CLASSIC ROUTER MODE: single-step, no verbose thinking
        print(f"⚡ {decision.get('reasoning', 'Direct operation')}")

        routing = route(user_input, context)

        if routing.get("error") == "ollama_offline":
            return "❌ Ollama is not running. Start it with: ollama serve"

        task = routing.get("task", user_input)

        from zonny.react_loop import run_react_agent
        result = run_react_agent(
            user_query=task,
            project_root=context.get("project_root", "."),
            max_iterations=10,
            verbose=False
        )
        return result


def print_help():
    """Print help information"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                     ZONNY HELP                               ║
╚══════════════════════════════════════════════════════════════╝

Commands:
  /exit, exit, quit    - Exit Zonny
  /help, help          - Show this help

Usage:
  Just type naturally! Zonny understands your intent.

Examples:
  • "list files"
  • "read server.py"
  • "tell me what this project is about"  (adaptive reasoning)
  • "analyze workspace and create report"
  • "what's the git status?"

Architecture (Phase 6):
  🧠 ReAct Mode (Default) - Adaptive reasoning
     Think → Act → Observe → Repeat
     • No assumptions about files
     • Self-corrects on errors
     • Gemini-level intelligence
     
  📋 Classic Mode - Plan → Execute → Reflect
     (Set ZONNY_REACT_MODE=false to use)

Working Directory:
  All operations happen in the directory where you ran 'zonny'.
  Files are read/written relative to that directory.

Current Mode:
  {'🧠 ReAct Mode (Adaptive)' if USE_REACT_MODE else '📋 Classic Mode'}

""")
