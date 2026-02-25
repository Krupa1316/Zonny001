"""
Zonny Reflector - Phase 2 Architecture

Verifies task completion and reasons about results.

This is the quality control agent that:
- Checks if goal was achieved
- Analyzes execution results
- Decides if retry needed
- Suggests next actions

Reflector reasons ABOUT execution - it doesn't execute.
"""

import json
import requests


# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"
TIMEOUT = 120


REFLECTOR_SYSTEM = """You are Zonny Reflector - An intelligent quality verifier.

Your job: Evaluate both COMPLETION and APPROACH QUALITY.

Input:
- Original goal
- Execution results (what was done)
- Optional: Planning reasoning

Analyze and determine:
1. Was the goal accomplished?
2. Was the approach smart and efficient?
3. Did it avoid unnecessary work?
4. What should happen next (if needed)?

EVALUATION CRITERIA:

Completion:
- Did the execution achieve what user wanted?
- If partial success, is it good enough?
- Were there critical failures?

Approach Quality:
- Did it waste computation (e.g., regenerating existing files)?
- Did it check context before acting?
- Was it adaptive or rigid?
- Were steps unnecessary?

Suggestions:
- If files missing, suggest existing alternatives
- If approach was inefficient, note better ways
- Be constructive and specific

Return ONLY valid JSON:

{
  "done": true/false,
  "reason": "<why complete or incomplete>",
  "approach_quality": "excellent|good|acceptable|poor",
  "efficiency_note": "<optional note on efficiency>",
  "confidence": 0.0-1.0,
  "next_action": "<what to do next, or null if done>"
}

Examples:

Goal: "summarize project"
Plan Reasoning: "analysis.txt exists (5.9KB), will read it"
Results: "Read analysis.txt successfully (5.9KB)"
→ {{"done": true, "reason": "Efficient - read existing analysis instead of regenerating", "approach_quality": "excellent", "efficiency_note": "Smart reuse of existing work", "confidence": 0.95, "next_action": null}}

Goal: "summarize project"
Plan Reasoning: "Will scan and create new report"
Results: "Created analysis.txt... but analysis.txt already existed"
→ {{"done": true, "reason": "Goal achieved but wasteful - regenerated existing analysis", "approach_quality": "poor", "efficiency_note": "Should have checked and read existing analysis.txt first", "confidence": 0.7, "next_action": null}}

Goal: "explain this project"
Plan Reasoning: "Will list files and read README.md"
Results: "Listed files... README.md not found"
→ {{"done": false, "reason": "README.md doesn't exist", "approach_quality": "acceptable", "efficiency_note": "Should check for alternatives like analysis.txt, setup.py", "confidence": 0.6, "next_action": "read analysis.txt or setup.py instead"}}

Goal: "list files"
Results: "[DIR] Files listed: 69 files"
→ {{"done": true, "reason": "Simple task completed efficiently", "approach_quality": "excellent", "confidence": 1.0, "next_action": null}}

Be honest about approach quality. Reward smart context-aware planning.
Output ONLY the JSON object, nothing else.
"""


def reflect(goal: str, execution: dict, context: dict = None) -> dict:
    """
    Reflect on execution results to verify goal completion AND approach quality.
    
    Args:
        goal: Original user goal
        execution: Execution result from executor
        context: Optional context including plan reasoning
        
    Returns:
        Reflection dict: {
            "done": bool,
            "reason": str,
            "approach_quality": str,
            "efficiency_note": str,
            "confidence": float,
            "next_action": str or None
        }
    """
    # Build reflection prompt with context
    results_summary = format_results_for_reflection(execution)
    
    # Include planning reasoning if available
    plan_reasoning = ""
    if context and isinstance(context.get("plan_obj"), dict):
        reasoning = context["plan_obj"].get("reasoning", "")
        if reasoning:
            plan_reasoning = f"\n\nPlanner's Reasoning:\n{reasoning}"
    
    prompt = f"""Goal:
{goal}
{plan_reasoning}

Execution Results:
{results_summary}

Evaluate if goal was completed AND if approach was smart.
"""

    try:
        # Call Ollama for reflection
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "system": REFLECTOR_SYSTEM,
                "stream": False,
                "temperature": 0.1 # Low temp for consistent evaluation
            },
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            # Fallback reflection
            return {
                "done": execution.get("success", False),
                "reason": "Unable to verify - Ollama error",
                "approach_quality": "acceptable",
                "efficiency_note": None,
                "confidence": 0.5,
                "next_action": None,
                "fallback": True
            }
        
        result = response.json()
        llm_output = result.get("response", "")
        
        # Parse JSON from LLM
        llm_output = llm_output.strip()
        
        # Remove markdown code blocks if present
        if llm_output.startswith("```"):
            lines = llm_output.split('\n')
            llm_output = '\n'.join(lines[1:-1]) if len(lines) > 2 else llm_output
        
        # Parse JSON
        reflection = json.loads(llm_output)
        
        # Validate reflection structure with new fields
        if "done" not in reflection:
            reflection["done"] = execution.get("success", False)
        
        if "reason" not in reflection:
            reflection["reason"] = "No reason provided"
        
        if "approach_quality" not in reflection:
            reflection["approach_quality"] = "acceptable"
        
        if "efficiency_note" not in reflection:
            reflection["efficiency_note"] = None
        
        if "confidence" not in reflection:
            reflection["confidence"] = 0.7
        
        if "next_action" not in reflection:
            reflection["next_action"] = None
        
        return reflection
        
    except requests.exceptions.ConnectionError:
        # Ollama offline - fallback to simple check
        return {
            "done": execution.get("success", False),
            "reason": "Ollama offline - basic check: execution " + 
                     ("succeeded" if execution.get("success") else "failed"),
            "approach_quality": "acceptable",
            "efficiency_note": None,
            "confidence": 0.6,
            "next_action": None,
            "fallback": True
        }
    
    except json.JSONDecodeError as e:
        # LLM didn't return valid JSON
        return {
            "done": execution.get("success", False),
            "reason": f"Reflection error - JSON parse failed: {e}",
            "approach_quality": "acceptable",
            "efficiency_note": None,
            "confidence": 0.5,
            "next_action": None,
            "fallback": True
        }
    
    except Exception as e:
        # Any other error
        return {
            "done": execution.get("success", False),
            "reason": f"Reflection error: {e}",
            "approach_quality": "acceptable",
            "efficiency_note": None,
            "confidence": 0.5,
            "next_action": None,
            "fallback": True
        }


def format_results_for_reflection(execution: dict) -> str:
    """
    Format execution results for reflector analysis.
    
    Args:
        execution: Result from executor
        
    Returns:
        Formatted string for LLM analysis
    """
    lines = []
    
    lines.append(f"Steps completed: {execution['steps_completed']}/{execution['total_steps']}")
    lines.append(f"Success: {execution['success']}")
    
    if execution.get("error"):
        lines.append(f"Error: {execution['error']}")
    
    lines.append("")
    lines.append("Step results:")
    
    for step_result in execution.get("results", []):
        step_num = step_result["step"]
        task = step_result["task"]
        tool = step_result["tool"]
        success = step_result["success"]
        result = step_result["result"]
        
        lines.append(f"\nStep {step_num}: {task} (tool: {tool})")
        lines.append(f"Success: {success}")
        
        # Show result (truncated)
        if isinstance(result, str):
            preview = result[:500] + "..." if len(result) > 500 else result
            lines.append(f"Result: {preview}")
    
    return "\n".join(lines)


def should_retry(reflection: dict) -> bool:
    """
    Determine if task should be retried based on reflection.
    
    Args:
        reflection: Result from reflect()
        
    Returns:
        True if retry recommended
    """
    # Don't retry if done
    if reflection.get("done"):
        return False
    
    # Retry if confidence is low and there's a suggested action
    if reflection.get("confidence", 1.0) < 0.7 and reflection.get("next_action"):
        return True
    
    return False
