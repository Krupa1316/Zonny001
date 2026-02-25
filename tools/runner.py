"""
Slice D - Tool Runner

Executes tool calls from agents.

This is the core execution engine that:
1. Parses tool call JSON
2. Gets tool from registry
3. Executes with args
4. Returns result

Tool Call Format:
{
    "tool": "read_file",
    "args": {"path": "server.py"}
}

Final Answer Format:
{
    "final": "Here is your answer"
}
"""

from tools.registry import get, is_allowed
import json


def run_tool(call: dict) -> str:
    """
    Execute a tool call.
    
    Args:
        call: Tool call dict with "tool" and "args"
        
    Returns:
        Tool execution result as string
        
    Raises:
        ValueError: If call format is invalid
        PermissionError: If tool not allowed
        Exception: If tool execution fails
    """
    # Validate call format
    if not isinstance(call, dict):
        raise ValueError("Tool call must be dict")
    
    if "tool" not in call:
        raise ValueError("Tool call missing 'tool' field")
    
    tool_name = call["tool"]
    args = call.get("args", {})
    
    # Security check
    if not is_allowed(tool_name):
        raise PermissionError(f"Tool '{tool_name}' not allowed")
    
    # Get tool function
    tool_func = get(tool_name)
    
    if tool_func is None:
        raise ValueError(f"Tool '{tool_name}' not found")
    
    # Execute tool
    try:
        result = tool_func(**args)
        return str(result)
    except Exception as e:
        return f"[FAIL] Tool error: {type(e).__name__}: {e}"


def parse_agent_output(output: str) -> dict:
    """
    Parse agent output to extract tool call or final answer.
    
    Agents can return either:
    - {"tool": "name", "args": {...}}
    - {"final": "answer"}
    
    Args:
        output: Agent output string
        
    Returns:
        Parsed dict with either "tool" or "final"
        
    Note:
        If output is plain text (not JSON), treats as final answer.
    """
    # Try to parse as JSON
    try:
        parsed = json.loads(output.strip())
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    
    # If not JSON, treat as final answer
    return {"final": output}


def execute_tool_loop(agent, initial_input: str, context: dict, max_iterations: int = 10) -> str:
    """
    Execute agent with tool loop.
    
    This is the core execution loop:
    1. Agent runs and returns output
    2. If output is tool call, execute tool
    3. Feed tool result back to agent
    4. Repeat until agent returns final answer or max iterations
    
    Args:
        agent: Agent instance
        initial_input: Initial user input
        context: Execution context
        max_iterations: Max tool iterations (default: 10)
        
    Returns:
        Final answer from agent
    """
    current_input = initial_input
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Run agent
        agent_output = agent.run(current_input, context)
        
        # Parse output
        parsed = parse_agent_output(agent_output)
        
        # Check if final answer
        if "final" in parsed:
            return parsed["final"]
        
        # Check if tool call
        if "tool" in parsed:
            try:
                # Execute tool
                tool_result = run_tool(parsed)
                
                # Feed result back to agent
                current_input = f"Tool '{parsed['tool']}' result:\n{tool_result}\n\nContinue or provide final answer."
                
            except Exception as e:
                # Tool error - feed back to agent
                current_input = f"Tool error: {e}\n\nTry another approach or provide final answer."
        else:
            # Unknown format - treat as final
            return agent_output
    
    return f"[WARN]️ Max iterations ({max_iterations}) reached. Tool loop stopped."
