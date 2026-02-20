"""
PlannerAgent - Uses LLM to create dynamic execution plans

This agent understands user intent and decomposes it into structured steps.
"""

import json
import requests
from runtime.base import BaseAgent

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"


class PlannerAgent(BaseAgent):
    """
    Planner Agent that uses Ollama LLM to generate execution plans.
    
    Rules:
    ✔ Produces structure (JSON plans)
    ✔ Never executes tools
    ✔ Never reads files
    ✔ Only decides what to do
    """
    
    name = "planner"

    def execute(self, context, task):
        """
        Generate an execution plan based on user task.
        
        Args:
            context: AgentContext (can be None for standalone testing)
            task: User's request string
            
        Returns:
            List of step dictionaries: [{"agent": "...", "action": "..."}]
        """
        
        prompt = f"""You are a task planner for a multi-agent system.

Available subagents:
- document_agent: Retrieves and processes documents (PDFs, text files) using vector search
- memory_agent: Recalls past conversations and context from vector database
- codebase_agent: Executes Python code and analyzes code files
- file_agent: Reads, writes, and searches files
- assistant_agent: Responds with natural language answers and synthesis

User request:
{task}

Analyze the request and create a plan. Return ONLY a valid JSON array of steps using "subagent" key.

Example plans:

For "summarize this pdf":
[
  {{"subagent": "document_agent"}},
  {{"subagent": "assistant_agent"}}
]

For "what did we discuss yesterday?":
[
  {{"subagent": "memory_agent"}},
  {{"subagent": "assistant_agent"}}
]

For "analyze the code in server.py":
[
  {{"subagent": "codebase_agent"}},
  {{"subagent": "assistant_agent"}}
]

Now create a plan for the user's request. Return ONLY the JSON array with "subagent" keys, nothing else.
"""

        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }

        try:
            # Call Ollama
            r = requests.post(OLLAMA_URL, json=payload, timeout=120)
            r.raise_for_status()
            
            # Parse response
            result = r.json()
            response_text = result.get("response", "").strip()
            
            # Extract JSON (handle potential markdown code blocks)
            if "```json" in response_text:
                # Extract from markdown code block
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                # Generic code block
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            plan = json.loads(response_text)
            
            # Validate it's a list
            if not isinstance(plan, list):
                raise ValueError("Plan must be a JSON array")
            
            # Validate each step has required fields
            for step in plan:
                if not isinstance(step, dict):
                    raise ValueError("Each step must be a dictionary")
                if "subagent" not in step:
                    raise ValueError("Each step must have 'subagent' field")
            
            return plan
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to call Ollama: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Planner returned invalid JSON: {e}\nResponse: {response_text}")
        except Exception as e:
            raise Exception(f"Planner error: {e}")
