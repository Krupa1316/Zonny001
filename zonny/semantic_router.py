"""
Zonny Router - Phase 1: Agent Intent Router

Single responsibility: Understand user intent, select agent, produce task.

The router ONLY:
  - Understands user intent
  - Selects the right agent
  - Produces a natural language task description

The router NEVER:
  - Outputs tool names
  - Calls tools
  - Executes anything
  - Accesses the filesystem

Flow:
  User -> Router -> {agent, task, intent, confidence, reasoning}
                        |
               Agent runs ReAct loop to execute the task
"""

import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"
TIMEOUT = 120

# Agent registry - router picks from these only
AGENTS = {
    "general": "General assistant. Conversations, questions, explanations, greetings, any topic.",
    "code": "Code expert. Exploring workspaces, reading files, understanding codebases, file operations.",
    "docs": "Document specialist. Querying uploaded PDFs and documentation files.",
    "memory": "Memory agent. Recalling past conversations, session history, previous context.",
}


def build_router_prompt():
    """Kept for backwards compatibility."""
    return _build_router_prompt()


def _build_router_prompt() -> str:
    agent_list = "\n".join(f"- {name}: {desc}" for name, desc in AGENTS.items())
    return f"""You are Zonny Router.

Your ONLY job: Read the user message. Choose the correct agent. Write a specific task.

Available agents:
{agent_list}

RULES:
1. Return ONLY valid JSON. No text before or after the JSON block.
2. Never output tool names (filesystem.list, workspace.scan, etc.).
3. Never execute anything yourself.
4. The "task" field must be a plain-English description for the agent - be specific.

Output format:
{{
  "intent": "<short label>",
  "agent": "<general|code|docs|memory>",
  "confidence": <0.0-1.0>,
  "reasoning": "<why this agent>",
  "task": "<specific task for the agent>"
}}

Examples:

User: "list files"
{{"intent":"list files","agent":"code","confidence":0.98,"reasoning":"file operations are code-agent territory","task":"List all files and directories in the current workspace"}}

User: "what does this project do?"
{{"intent":"understand project","agent":"code","confidence":0.95,"reasoning":"requires reading source files","task":"Explore the workspace by reading README, config files, and key source files, then explain what this project does and its architecture"}}

User: "read server.py"
{{"intent":"read file","agent":"code","confidence":0.99,"reasoning":"specific file read request","task":"Read and display the full contents of server.py"}}

User: "summarize the codebase"
{{"intent":"summarize project","agent":"code","confidence":0.95,"reasoning":"requires file exploration","task":"Read all major source files and provide a detailed summary of the project architecture, technologies used, and purpose"}}

User: "hello"
{{"intent":"greeting","agent":"general","confidence":1.0,"reasoning":"simple greeting","task":"Respond to a friendly greeting"}}

User: "search docs for authentication"
{{"intent":"query documents","agent":"docs","confidence":0.9,"reasoning":"searching uploaded documents","task":"Search uploaded documents for information about authentication"}}

User: "what did we talk about before?"
{{"intent":"recall history","agent":"memory","confidence":0.88,"reasoning":"asking about past conversation","task":"Recall and summarize the recent conversation history for this session"}}

Route this input:"""


def route(user_input: str, context: dict = None) -> dict:
    """
    Route user input to an agent intent.

    Args:
        user_input: Natural language from user
        context: Optional session context

    Returns:
        {
            "intent": str,
            "agent": str,        # one of: general, code, docs, memory
            "confidence": float,
            "reasoning": str,
            "task": str          # plain-English task passed to the agent
        }
    """
    system_prompt = _build_router_prompt()

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": user_input,
                "system": system_prompt,
                "stream": False,
                "temperature": 0.05,
                "format": "json"
            },
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            return _fallback_route(user_input)

        llm_output = response.json().get("response", "").strip()

        if "{" not in llm_output:
            return _fallback_route(user_input)

        start = llm_output.index("{")
        brace_count = 0
        end = -1
        for i in range(start, len(llm_output)):
            if llm_output[i] == "{":
                brace_count += 1
            elif llm_output[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        if end == -1:
            return _fallback_route(user_input)

        intent = json.loads(llm_output[start:end])

        # Validate and fill missing fields
        if "agent" not in intent or intent["agent"] not in AGENTS:
            intent["agent"] = "general"
        if "task" not in intent or not intent["task"]:
            intent["task"] = user_input
        if "intent" not in intent:
            intent["intent"] = "unknown"
        if "confidence" not in intent:
            intent["confidence"] = 0.5
        if "reasoning" not in intent:
            intent["reasoning"] = "router"

        # Safety: strip any accidental tool keys router should not output
        intent.pop("tool", None)
        intent.pop("args", None)

        return intent

    except requests.exceptions.ConnectionError:
        return {
            "intent": "unknown",
            "agent": "general",
            "confidence": 0.0,
            "reasoning": "Ollama offline",
            "task": user_input,
            "error": "ollama_offline"
        }

    except Exception as e:
        return _fallback_route(user_input, str(e))


def _fallback_route(user_input: str, error: str = "") -> dict:
    """Last-resort fallback when LLM is unreachable."""
    inp = user_input.lower()
    if any(w in inp for w in ["file", "read", "list", "code", "project", "workspace", "directory", "folder"]):
        agent = "code"
    elif any(w in inp for w in ["pdf", "document", "search doc"]):
        agent = "docs"
    elif any(w in inp for w in ["remember", "recall", "history", "before", "earlier"]):
        agent = "memory"
    else:
        agent = "general"

    return {
        "intent": "fallback",
        "agent": agent,
        "confidence": 0.2,
        "reasoning": f"LLM fallback{': ' + error if error else ''}",
        "task": user_input
    }
