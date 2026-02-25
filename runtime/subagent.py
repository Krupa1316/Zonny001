"""
SubAgentRunner - Independent cognitive loops for subagents

Each subagent runs in its own isolated context with:
- Its own system prompt
- Local memory
- Think + act loop
- Tool calling capability
- Iteration limits

This is Gemini-style subagent behavior.
"""

import json
import requests
from typing import Dict, Any, List, Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"


class SubAgentRunner:
    """
    Runs a subagent with independent cognitive loop.
    
    The subagent:
    - Thinks multiple steps
    - Calls tools
    - Maintains local memory
    - Returns when done or max iterations reached
    """
    
    def __init__(self, manifest: Dict[str, Any], tools: Dict[str, Any]):
        """
        Initialize subagent runner.
        
        Args:
            manifest: Agent manifest dictionary (from YAML)
            tools: Dictionary of available tools {name: tool_instance}
        """
        self.manifest = manifest
        self.tools = tools
        self.local_memory: List[str] = []
        self.iteration = 0
    
    def run(self, task: str) -> str:
        """
        Run the subagent on a task.
        
        The agent loops:
        1. Receives task + memory
        2. Decides: call tool OR return final answer
        3. If tool: execute, store result in memory, loop
        4. If final: return answer
        
        Args:
            task: The task for this subagent
            
        Returns:
            Final answer from the subagent
        """
        max_iters = self.manifest.get("max_iterations", 4)
        agent_name = self.manifest.get("name", "unknown")
        
        print(f"\n[BOT] SubAgent '{agent_name}' started")
        print(f" Task: {task}")
        print(f" Max iterations: {max_iters}")
        
        for step in range(max_iters):
            self.iteration = step + 1
            print(f"\n Iteration {self.iteration}/{max_iters}...")
            
            # Build memory context (last 5 entries)
            memory_block = "\n".join(self.local_memory[-5:]) if self.local_memory else "None"
            
            # Build prompt
            prompt = f"""{self.manifest['system_prompt']}

Available tools: {', '.join(self.tools.keys())}

Previous internal results:
{memory_block}

Current task:
{task}

You must respond in EXACTLY one of these formats:

TOOL:<tool_name>:<input>
(To call a tool and get information)

FINAL:<answer>
(To return your final answer)

Examples:
TOOL:vector_search:machine learning documents
FINAL:Based on the documents, machine learning is...

Choose your next action:"""
            
            # Call LLM
            try:
                payload = {
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False
                }
                
                r = requests.post(OLLAMA_URL, json=payload, timeout=120)
                r.raise_for_status()
                
                result = r.json()
                reply = result.get("response", "").strip()
                
                print(f" Agent says: {reply[:100]}...")
                
            except Exception as e:
                error_msg = f"LLM call failed: {e}"
                print(f" [FAIL] {error_msg}")
                self.local_memory.append(error_msg)
                continue
            
            # Parse response
            
            # FINAL ANSWER
            if reply.startswith("FINAL:"):
                final_answer = reply.replace("FINAL:", "").strip()
                print(f" [OK] Final answer ready")
                return final_answer
            
            # TOOL CALL
            if reply.startswith("TOOL:"):
                parts = reply.split(":", 2)
                if len(parts) >= 3:
                    _, tool_name, tool_input = parts
                    tool_name = tool_name.strip()
                    tool_input = tool_input.strip()
                    
                    print(f" [FIX] Calling tool: {tool_name}")
                    print(f" Input: {tool_input[:50]}...")
                    
                    # Get tool
                    tool = self.tools.get(tool_name)
                    if not tool:
                        error_msg = f"Tool '{tool_name}' not found. Available: {list(self.tools.keys())}"
                        print(f" [FAIL] {error_msg}")
                        self.local_memory.append(error_msg)
                        continue
                    
                    # Execute tool
                    try:
                        result = tool.execute(tool_input)
                        result_str = str(result)[:200] # Limit memory size
                        self.local_memory.append(f"[{tool_name}] {result_str}")
                        print(f" [OK] Tool result: {result_str[:80]}...")
                    except Exception as e:
                        error_msg = f"Tool '{tool_name}' error: {e}"
                        print(f" [FAIL] {error_msg}")
                        self.local_memory.append(error_msg)
                    
                    continue
                else:
                    error_msg = "Invalid TOOL format. Use: TOOL:<name>:<input>"
                    print(f" [FAIL] {error_msg}")
                    self.local_memory.append(error_msg)
                    continue
            
            # Unknown format - treat as thought/reasoning
            print(f" [CHAT] Agent thinking: {reply[:80]}...")
            self.local_memory.append(reply[:200])
        
        # Max iterations reached
        final_answer = f"[{agent_name}] Max iterations ({max_iters}) reached. Last memory: {self.local_memory[-1] if self.local_memory else 'none'}"
        print(f"\n ⏱️ Iteration limit reached")
        return final_answer
    
    def get_memory(self) -> List[str]:
        """Get the subagent's local memory"""
        return self.local_memory.copy()
    
    def clear_memory(self):
        """Clear the subagent's local memory"""
        self.local_memory.clear()
        self.iteration = 0
