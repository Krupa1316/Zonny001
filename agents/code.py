"""
Slice E - Code Agent with Tool Support + LLM

Now includes:
- Tool invocation (read files, list directory)
- JSON-based tool protocol
- Deterministic tool selection (keyword-based)
- LLM responses for code analysis

Tool Protocol:
- Agent returns: {"tool": "name", "args": {...}}
- Or returns: {"final": "answer"}

Slice E Implementation:
- Keyword matching decides which tool to use
- Ollama generates intelligent code responses
"""

from agents.base import Agent
from zonny.memory import store, retrieve
import json
import os
import requests


class CodeAgent(Agent):
    """
    Code Agent - Handles code and programming queries.
    
    Slice D: Can invoke tools to read/write files.
    """
    
    name = "code"
    description = "Handles code and programming queries with filesystem access"
    
    def __init__(self):
        super().__init__()
        self.tool_used = False  # Track if we've used a tool
    
    def run(self, input: str, context: dict) -> str:
        """
        Handle code queries with tool support.
        
        Tool Protocol:
        - Returns JSON string with tool call or final answer
        - {"tool": "read_file", "args": {"path": "server.py"}}
        - {"final": "Here is your answer"}
        
        Args:
            input: User input or tool result
            context: Execution context (must include session)
            
        Returns:
            JSON string with tool call or final answer
        """
        session = context.get('session', 'unknown')
        
        # Check if this is a tool result (feedback loop)
        if "Tool '" in input and " result:" in input:
            # We got tool output - use LLM for intelligent response
            self.tool_used = False  # Reset for next query
            
            # Extract tool output
            lines = input.split('\n')
            tool_output = '\n'.join(lines[1:]) if len(lines) > 1 else input  # Skip first line
            
            # Store tool result in memory
            store(tool_output[:500], session, self.name, "assistant")
            
            # Slice E: Use LLM to format/analyze tool result
            system_prompt = f"""You are a code assistant (Code Agent).
You just executed a tool and got this result:

{tool_output[:2000]}

Provide a clear, helpful response to the user based on this tool output.
Be concise but informative."""
            
            try:
                llm_response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "nemotron-3-nano:latest",
                        "prompt": "Summarize and present this tool result to the user in a helpful way.",
                        "system": system_prompt,
                        "stream": False
                    },
                    timeout=120
                )
                
                if llm_response.status_code == 200:
                    result = llm_response.json()
                    final_answer = result.get("response", tool_output[:1000])
                else:
                    # Fallback to raw output
                    final_answer = f"💻 Tool Result:\n\n{tool_output[:1000]}"
            except:
                # Fallback to raw output
                final_answer = f"💻 Tool Result:\n\n{tool_output[:1000]}"
            
            return json.dumps({"final": final_answer})
        
        # Retrieve code-related memories
        code_memories = retrieve(input, session, self.name, k=2)
        
        # Store user query
        store(input, session, self.name, "user")
        
        # Slice D: Deterministic tool selection (keyword-based)
        # Later replaced by LLM
        
        input_lower = input.lower()
        
        # Tool dispatch: read_file
        if ("open" in input_lower or "read" in input_lower or "show" in input_lower) and \
           ("file" in input_lower or "code" in input_lower or ".py" in input_lower or ".js" in input_lower):
            
            # Extract filename if mentioned
            filename = None
            for word in input.split():
                if "." in word and "/" not in word:  # Simple filename detection
                    filename = word.strip('.,!?')
                    break
            
            if not filename:
                filename = "server.py"  # Default file
            
            tool_call = {
                "tool": "read_file",
                "args": {"path": filename}
            }
            
            self.tool_used = True
            return json.dumps(tool_call)
        
        # Tool dispatch: list_files
        if "list" in input_lower and ("file" in input_lower or "folder" in input_lower or "directory" in input_lower):
            
            tool_call = {
                "tool": "list_files",
                "args": {"directory": "."}
            }
            
            self.tool_used = True
            return json.dumps(tool_call)
        
        # Tool dispatch: search_files
        if "search" in input_lower or "find" in input_lower:
            
            # Extract pattern
            pattern = "*.py"  # Default pattern
            if ".py" in input_lower:
                pattern = "*.py"
            elif ".js" in input_lower:
                pattern = "*.js"
            elif ".json" in input_lower:
                pattern = "*.json"
            
            tool_call = {
                "tool": "search_files",
                "args": {"pattern": pattern, "directory": "."}
            }
            
            self.tool_used = True
            return json.dumps(tool_call)
        
        # No tool needed - use LLM for intelligent code response
        memory_context = ""
        if code_memories:
            memory_context = "\n\nPrevious code-related context:\n"
            for mem in code_memories[:2]:
                memory_context += f"- {mem}\n"
        
        # Slice E: Call Ollama for code analysis
        workspace_context = ""
        if context.get('files'):
            workspace_context = f"\n\nCurrent workspace has {len(context.get('files', []))} files."
        
        system_prompt = f"""You are a code assistant (Code Agent).
You help with programming, debugging, and code analysis.

You have access to tools to read/write/search files.
For now, provide helpful code guidance.{memory_context}{workspace_context}"""
        
        try:
            llm_response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "nemotron-3-nano:latest",
                    "prompt": input,
                    "system": system_prompt,
                    "stream": False
                },
                timeout=120
            )
            
            if llm_response.status_code == 200:
                result = llm_response.json()
                final_answer = result.get("response", "No response from LLM")
            else:
                final_answer = f"❌ LLM error: {llm_response.status_code}"
        except Exception as e:
            final_answer = f"❌ Error: {e}"
        
        # Store response
        store(final_answer, session, self.name, "assistant")
        
        return json.dumps({"final": final_answer})
