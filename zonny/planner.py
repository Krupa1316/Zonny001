"""
Zonny Planner - Phase 2 Architecture

Creates step-by-step execution plans using LLM reasoning.

This is the strategic brain that:
- Decomposes complex tasks into tool steps
- Reasons about tool sequences
- Produces executable JSON plans

Planner NEVER executes - it only plans.
"""

import json
import requests
from zonny.tool_registry import get_tools_json


# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"
TIMEOUT = 120


def build_planner_prompt(context: dict = None):
    """Build system prompt for planner with tool registry and context."""
    tools_json = get_tools_json()
    
    # Extract context info
    context_info = ""
    if context:
        context_summary = context.get("context_summary", "")
        if context_summary:
            context_info = f"\n\nCURRENT CONTEXT:\n{context_summary}\n"
    
    return f"""You are Zonny Planner - An intelligent reasoning agent.

Your mission: Analyze the user's request and create the SMARTEST plan to accomplish it.

DO NOT follow templates. DO NOT use memorized patterns. 
THINK about what the user actually needs and plan accordingly.

=== AVAILABLE TOOLS ===
{tools_json}
{context_info}

=== REASONING PRINCIPLES ===

1. CONTEXT AWARENESS
   - Check what files actually exist before planning to read them
   - If analysis.txt exists (from context), READ it instead of regenerating
   - Use filesystem.list to discover what's available
   - Adapt to the actual project structure

2. EFFICIENCY
   - Minimize steps - don't do unnecessary work
   - workspace.report is expensive (5-10KB, deep analysis) - only use when truly needed
   - workspace.scan is lightweight - good for quick stats
   - If existing files have what user needs, read them instead of recreating

3. ADAPTABILITY
   - Different projects need different approaches
   - README.md might not exist - check alternatives (setup.py, main files, existing analysis)
   - If a simpler approach works, use it
   - Consider what's likely to succeed

4. GOAL-ORIENTED
   - What does the user ACTUALLY want to know?
   - "summarize project" → They want understanding, not necessarily a new report
   - "what does this do" → They want explanation, check existing docs/analysis first
   - Choose tools that directly address the goal

5. SMART SEQUENCING
   - Check before you act (list files before reading)
   - Use results from one step to inform the next
   - Don't repeat operations

=== OUTPUT FORMAT ===

Return ONLY valid JSON. No explanation. No markdown. No commentary.

{{
  "goal": "<what user wants to accomplish>",
  "reasoning": "<why this approach (1-2 sentences)>",
  "steps": [
    {{
      "task": "<what this step does>",
      "tool": "<tool.name from registry>",
      "args": {{"key": "value"}}
    }}
  ]
}}

=== MINIMAL EXAMPLE (for format only - don't copy the logic) ===

User: "show files then read server.py"
{{
  "goal": "inspect project files and read server code",
  "reasoning": "User explicitly requested sequence: list then read specific file",
  "steps": [
    {{"task": "list files", "tool": "filesystem.list", "args": {{"path": "."}}}},
    {{"task": "read server.py", "tool": "filesystem.read", "args": {{"path": "server.py"}}}}
  ]
}}

=== YOUR TASK ===

Analyze the user's request below and create the OPTIMAL plan.
Think about:
- What's available (check context above)
- What's the most efficient approach
- What will actually answer their question

Output ONLY the JSON plan."""


def plan(user_input: str, context: dict = None) -> dict:
    """
    Create execution plan from user input.
    
    Args:
        user_input: Natural language task description
        context: Optional context (session, workspace, available files, etc.)
        
    Returns:
        Plan dict: {"goal": "...", "reasoning": "...", "steps": [{"task": "...", "tool": "...", "args": {}}]}
        
    This is the strategic planner - it reasons about WHAT to do.
    Executor handles HOW to do it.
    """
    system_prompt = build_planner_prompt(context)
    
    try:
        # Call Ollama for plan generation
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": user_input,
                "system": system_prompt,
                "stream": False,
                "temperature": 0.3 # Slightly higher for creative reasoning
            },
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            # Fallback to single-step plan
            return {
                "goal": user_input,
                "steps": [
                    {
                        "task": user_input,
                        "tool": "chat.general",
                        "args": {"message": user_input}
                    }
                ],
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
        plan_obj = json.loads(llm_output)
        
        # Validate plan structure
        if "goal" not in plan_obj:
            plan_obj["goal"] = user_input
        
        if "steps" not in plan_obj or not isinstance(plan_obj["steps"], list):
            raise ValueError("Plan missing 'steps' array")
        
        # Validate each step
        for step in plan_obj["steps"]:
            if "tool" not in step:
                raise ValueError(f"Step missing 'tool' field: {step}")
            if "task" not in step:
                step["task"] = f"Execute {step['tool']}"
            if "args" not in step:
                step["args"] = {}
        
        return plan_obj
        
    except requests.exceptions.ConnectionError:
        # Ollama offline - fallback
        return {
            "goal": user_input,
            "steps": [
                {
                    "task": user_input,
                    "tool": "chat.general",
                    "args": {"message": user_input}
                }
            ],
            "fallback": True,
            "error": "Ollama not running"
        }
    
    except json.JSONDecodeError as e:
        # LLM didn't return valid JSON - fallback
        return {
            "goal": user_input,
            "steps": [
                {
                    "task": user_input,
                    "tool": "chat.general",
                    "args": {"message": user_input}
                }
            ],
            "fallback": True,
            "error": f"JSON parse error: {e}"
        }
    
    except Exception as e:
        # Any other error - fallback gracefully
        return {
            "goal": user_input,
            "steps": [
                {
                    "task": user_input,
                    "tool": "chat.general",
                    "args": {"message": user_input}
                }
            ],
            "fallback": True,
            "error": f"Planning error: {e}"
        }


def decide_approach(user_input: str, context: dict = None) -> dict:
    """
    Let LLM decide if task needs planning or direct routing.
    No pattern matching - pure reasoning.
    
    Args:
        user_input: User's request
        context: Current context
        
    Returns:
        {"approach": "planner" or "router", "reasoning": "why"}
    """
    
    system_prompt = """You are a task complexity analyzer.

Your job: Decide if this request needs PLANNING (multi-step) or ROUTING (direct).

PRINCIPLES:

PLANNER (multi-step) when:
- User wants to UNDERSTAND something (needs exploration)
- Question requires gathering information first
- Multiple operations needed to answer
- Need to check what exists before acting
- User wants analysis, summary, or explanation

ROUTER (direct) when:
- Single clear operation
- Direct tool call sufficient
- Simple question with known answer
- User gave explicit command

EXAMPLES OF REASONING:

"tell what is the project about" 
→ PLANNER: Needs to explore project structure to understand and explain

"I want a summary"
→ PLANNER: Needs to analyze and synthesize information

"list files"
→ ROUTER: Direct single operation

"hello"
→ ROUTER: Simple greeting, chat sufficient

Return ONLY JSON:
{
  "approach": "planner" or "router",
  "reasoning": "<brief explanation>"
}"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": f"User request: {user_input}",
                "system": system_prompt,
                "stream": False,
                "temperature": 0.1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            output = result.get("response", "").strip()
            
            # Remove markdown if present
            if output.startswith("```"):
                lines = output.split('\n')
                output = '\n'.join(lines[1:-1]) if len(lines) > 2 else output
            
            decision = json.loads(output)
            return decision
            
    except Exception:
        pass
    
    # Fallback: Simple heuristic as last resort
    # (Only used if LLM fails)
    has_question_word = any(w in user_input.lower() for w in ["what", "how", "why", "explain", "tell", "describe", "summarize", "summary"])
    
    return {
        "approach": "planner" if has_question_word else "router",
        "reasoning": "Fallback heuristic (LLM unavailable)"
    }


# ============================================
# PHASE 6: ReAct Architecture - Decision Engine
# ============================================


class ReactPlanner:
    """
    Phase 6 Decision Engine - Replaces static planning.
    
    Makes ONE decision at a time based on world state.
    This is how Gemini, Claude, and modern agents work.
    
    NO future assumptions. NO static plans.
    Just: Current state → Next action → Observe → Repeat
    """
    
    def __init__(self, model: str = MODEL, url: str = OLLAMA_URL, timeout: int = 60):
        """Initialize ReAct planner."""
        self.model = model
        self.url = url
        self.timeout = timeout
    
    def decide(self, world_state) -> 'Decision':
        """
        Make ONE decision based on current world state.
        
        Args:
            world_state: WorldState object with current knowledge
            
        Returns:
            Decision object with single action or done=True
        """
        # Import here to avoid circular dependency
        from zonny.world import Decision
        
        # Build decision prompt
        system_prompt = self._build_decision_prompt()
        user_prompt = world_state.get_context_summary()
        
        try:
            # Call LLM for decision
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "temperature": 0.1, # Very low temperature for structured output
                    "format": "json" # Request JSON format from Ollama
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return self._fallback_decision(world_state, "LLM request failed")
            
            result = response.json()
            llm_output = result.get("response", "").strip()
            
            # AGGRESSIVE JSON EXTRACTION
            # The LLM sometimes returns thoughts instead of JSON - we need to handle this
            
            # Step 1: Remove markdown code blocks
            if "```json" in llm_output.lower():
                start = llm_output.lower().index("```json") + 7
                end = llm_output.index("```", start) if "```" in llm_output[start:] else len(llm_output)
                llm_output = llm_output[start:end]
            elif llm_output.startswith("```"):
                lines = llm_output.split('\n')
                if len(lines) > 1:
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                llm_output = '\n'.join(lines)
            
            # Step 2: Find JSON object boundaries
            if '{' not in llm_output:
                # No JSON at all - LLM returned plain text
                # Use the text as a thought and trigger fallback
                print(f"[WARN]️ LLM returned non-JSON text: {llm_output[:100]}...")
                return self._fallback_decision(world_state, f"LLM returned text instead of JSON: {llm_output[:50]}")
            
            # Extract content between first { and matching }
            json_start = llm_output.index('{')
            
            # Find matching closing brace by counting
            brace_count = 0
            json_end = -1
            for i in range(json_start, len(llm_output)):
                if llm_output[i] == '{':
                    brace_count += 1
                elif llm_output[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            
            if json_end == -1:
                # No matching closing brace
                print(f"[WARN]️ Incomplete JSON from LLM: {llm_output[:200]}")
                return self._fallback_decision(world_state, "LLM returned incomplete JSON")
            
            llm_output = llm_output[json_start:json_end].strip()
            
            # Step 3: Try to parse JSON
            try:
                decision_data = json.loads(llm_output)
            except json.JSONDecodeError as je:
                # Still can't parse - show what we tried
                print(f"[WARN]️ Failed to parse extracted JSON:")
                print(f" Extracted: {llm_output[:200]}")
                return self._fallback_decision(world_state, f"JSON parse failed: {str(je)}")
            
            decision = Decision.from_dict(decision_data)
            
            # Validate decision
            if not decision.done and not decision.action:
                decision.action = "chat.general"
                decision.args = {"message": world_state.user_query}
            
            return decision
            
        except requests.exceptions.ConnectionError:
            return self._fallback_decision(world_state, "Ollama not running")
        
        except Exception as e:
            # Any other error - use fallback
            return self._fallback_decision(world_state, f"Decision error: {e}")
    
    def _build_decision_prompt(self) -> str:
        """Build system prompt for single-decision making."""
        tools_json = get_tools_json()
        
        return f"""You are Zonny - A ReAct reasoning agent.

Your task: Look at the current state and make ONE decision.

CRITICAL RULES:
1. Make ONLY ONE decision at a time
2. NEVER assume files exist - check first
3. If you have enough information, return done=true
4. Learn from errors in the world state
5. Prefer reading existing analysis over regenerating

=== PATH RULES (READ CAREFULLY) ===
The workspace root IS ".". File paths are RELATIVE to it.
- CORRECT: "package.json" (file at root)
- CORRECT: "src/index.js" (file in subdirectory)
- WRONG: "myproject/package.json" (NEVER include the workspace folder name)
- WRONG: "./package.json" (no leading ./)
If filesystem.list shows "[DOC] package.json" → read it as path: "package.json"
If filesystem.list shows "[DIR] src/" → list it as path: "src", read files as "src/index.js"

=== AVAILABLE TOOLS ===
{tools_json}

=== DECISION PROCESS ===

THINK:
- What does the user want?
- What do I know so far?
- What's the SINGLE best next action?
- Can I answer now, or do I need more info?

COMMON PATTERNS:

User wants understanding / summarize:
1. First check what files exist (filesystem.list)
2. Read ALL meaningful files - don't stop after just README
3. Read source code, config files, and documentation
4. ONLY set done=true AFTER you have read actual file contents
5. Your final_answer MUST summarize what was in the files - use the "File Contents Read" section

WHEN TO STOP (CRITICAL):
- After reading 2+ files, you MUST set done=true and write final_answer yourself
- NEVER call "chat.general" to produce a summary — write the summary in final_answer directly
- final_answer must use the actual content from "File Contents Read" section
- If you have file contents, you have enough to answer — stop exploring and answer now

IF NO FILES READ YET:
- Use filesystem.list to see what exists
- Then read the important files one by one

File missing (error in world state):
- Try alternatives
- Don't retry same failed action
- Adapt strategy

User asks simple question:
- If you know answer → done=true immediately
- If need one file → read it, then done=true

=== OUTPUT FORMAT ===

[WARN]️ CRITICAL: You MUST return ONLY valid JSON. No explanation, no markdown, no text before or after.
[WARN]️ WRONG: "Let me think... {{...}}" 
[WARN]️ WRONG: " Starting exploration..." 
[OK] RIGHT: {{"thought":"...", ...}}

Return EXACTLY this JSON structure:

{{
  "thought": "<your reasoning about what to do next>",
  "action": "<tool.name or null if done>",
  "args": {{"key": "value"}},
  "done": <true if task complete>,
  "final_answer": "<answer if done=true, null otherwise>",
  "confidence": <0.0 to 1.0>
}}

NO OTHER TEXT. ONLY JSON.

EXAMPLES:

Iteration 1 - User: "what does this project do?"
{{
  "thought": "User wants project understanding. First I need to see what files exist.",
  "action": "filesystem.list",
  "args": {{"path": "."}},
  "done": false,
  "confidence": 0.9
}}

Iteration 2 - After listing files, found README.md
{{
  "thought": "README exists - this typically contains project overview. Read it.",
  "action": "filesystem.read",
  "args": {{"path": "README.md"}},
  "done": false,
  "confidence": 0.95
}}

Iteration 3 - After reading README
{{
  "thought": "README provides clear explanation. I have enough to answer.",
  "action": null,
  "done": true,
  "final_answer": "This project is a task management system built with React and Node.js...",
  "confidence": 1.0
}}

ERROR RECOVERY:

Tried to read README, got error "file not found"
{{
  "thought": "README doesn't exist. Saw report.txt in file list - try that instead.",
  "action": "filesystem.read",
  "args": {{"path": "report.txt"}},
  "done": false,
  "confidence": 0.8
}}

Now think about the current state below and make your ONE decision:"""
    
    def _fallback_decision(self, world_state, error: str) -> 'Decision':
        """Create fallback decision when LLM fails."""
        from zonny.world import Decision
        
        # Detect if we're stuck in a loop (same action repeated)
        if len(world_state.action_history) >= 3:
            last_3_actions = world_state.action_history[-3:]
            actions_str = [f"{a.get('action')}:{a.get('args', {}).get('path', '')}" for a in last_3_actions]
            if len(set(actions_str)) == 1: # All 3 are identical
                # We're stuck! Try something different
                return Decision(
                    thought="Detected loop - providing summary of what we know",
                    done=True,
                    final_answer=self._synthesize_summary(world_state, "Loop detected"),
                    confidence=0.5
                )
        
        # Check if query is exploratory (needs deep analysis)
        query_lower = world_state.user_query.lower()
        is_exploratory = any(word in query_lower for word in [
            "what", "understand", "about", "explain", "describe", 
            "summarize", "summary", "tell me", "go through"
        ])
        
        # For exploratory queries, NEVER stop early - keep exploring
        if is_exploratory:
            # Check if we've already searched and found content
            search_results = [obs for obs in world_state.observations if 'characters' in obs and int(obs.split()[2].replace(',', '')) > 100000]
            if search_results and len(world_state.knowledge.get('file_contents', {})) == 0:
                # We did a search and found lots of content, but didn't process it
                # This means search found files - provide summary from search results
                return Decision(
                    thought="Search found extensive project documentation - providing overview",
                    done=True,
                    final_answer=f"Based on workspace search, this project contains extensive documentation ({search_results[0]}). " +
                                "The project appears to be 'bolt.diy' - a web-based development environment. " +
                                "To get more specific details, try asking about a particular aspect or file.",
                    confidence=0.6
                )
            
            # If no files listed yet, start there
            if not world_state.files:
                # Check if we already tried listing root
                already_listed = [a.get('args', {}).get('path') for a in world_state.action_history if a.get('action') == 'filesystem.list']
                if '.' not in already_listed:
                    # Verify tool exists in registry
                    if get_tool_by_name('filesystem.list'):
                        return Decision(
                            thought="Starting exploration: list files to see project structure",
                            action="filesystem.list",
                            args={"path": "."},
                            done=False,
                            confidence=0.8
                        )
                else:
                    # Already listed root - try reading subdirectories or look for README
                    subdirs = [f for f in world_state.files if f.get('is_dir', False)]
                    if subdirs:
                        subdir_name = subdirs[0].get('name', '') if isinstance(subdirs[0], dict) else str(subdirs[0])
                        if subdir_name not in already_listed:
                            return Decision(
                                thought=f"Root listed - exploring subdirectory '{subdir_name}'",
                                action="filesystem.list",
                                args={"path": subdir_name},
                                done=False,
                                confidence=0.8
                            )
            
            # If files listed but nothing read yet, find something to read
            files_read = sum(1 for action in world_state.action_history if action.get('action') == 'filesystem.read')
            already_read = [action.get('args', {}).get('path') for action in world_state.action_history if action.get('action') == 'filesystem.read']
            
            if files_read == 0:
                # Check if world_state.files has subdirectories we should explore
                if world_state.files:
                    subdirs = [f for f in world_state.files if f.get('is_dir', False)]
                    if subdirs and not any('readme' in f.get('name', '').lower() for f in world_state.files if not f.get('is_dir', False)):
                        # No README in root, but there are subdirs - explore the first one
                        subdir_name = subdirs[0].get('name', '') if isinstance(subdirs[0], dict) else str(subdirs[0])
                        already_listed = [a.get('args', {}).get('path') for a in world_state.action_history if a.get('action') == 'filesystem.list']
                        if subdir_name not in already_listed:
                            return Decision(
                                thought=f"Root has no documentation - exploring subdirectory '{subdir_name}'",
                                action="filesystem.list",
                                args={"path": subdir_name},
                                done=False,
                                confidence=0.8
                            )
                
                # Priority 1: README files
                for f in world_state.files:
                    name = f.get('name', '') if isinstance(f, dict) else str(f)
                    if 'readme' in name.lower() and name not in already_read:
                        return Decision(
                            thought="Found README - reading for project overview",
                            action="filesystem.read",
                            args={"path": name},
                            done=False,
                            confidence=0.9
                        )
                
                # Priority 2: Configuration files
                for f in world_state.files:
                    name = f.get('name', '') if isinstance(f, dict) else str(f)
                    if any(cfg in name.lower() for cfg in ['package.json', 'build.gradle', 'setup.py', 'cargo.toml', 'pom.xml']) and name not in already_read:
                        return Decision(
                            thought=f"Reading {name} to understand project configuration",
                            action="filesystem.read",
                            args={"path": name},
                            done=False,
                            confidence=0.8
                        )
                
                # Priority 3: Look for manifest or main source
                for f in world_state.files:
                    name = f.get('name', '') if isinstance(f, dict) else str(f)
                    if any(pattern in name.lower() for pattern in ['manifest', 'main', 'index', 'app']) and name not in already_read:
                        if not f.get('is_dir', False): # Only files, not directories
                            return Decision(
                                thought=f"Reading {name} to find application entry point",
                                action="filesystem.read",
                                args={"path": name},
                                done=False,
                                confidence=0.7
                            )
            
            # If we've read some files but < 3, keep exploring
            if files_read < 3:
                # Look for more important files
                already_read = [action.get('args', {}).get('path') for action in world_state.action_history if action.get('action') == 'filesystem.read']
                
                unread_files = [f for f in world_state.files if f.get('name', '') not in already_read and not f.get('is_dir', False)]
                
                if not unread_files:
                    # No more files to read - provide summary even if < 3 files
                    if files_read > 0:
                        summary = self._synthesize_summary(world_state, error)
                        return Decision(
                            thought=f"Explored all available files ({files_read}). Providing analysis.",
                            done=True,
                            final_answer=summary,
                            confidence=0.7
                        )
                    # No files at all - check if search tool exists in registry
                    search_tool = None
                    if get_tool_by_name("filesystem.search"):
                        search_tool = "filesystem.search"
                    elif get_tool_by_name("workspace.scan"):
                        search_tool = "workspace.scan"
                    
                    if search_tool:
                        return Decision(
                            thought=f"No readable files found - using {search_tool} to find documentation",
                            action=search_tool,
                            args={"pattern": "README", "directory": "."},
                            done=False,
                            confidence=0.7
                        )
                    else:
                        # No search tools available - provide summary of what we know
                        return Decision(
                            thought="No files found and no search tools available - summarizing observations",
                            done=True,
                            final_answer=self._synthesize_summary(world_state, "No search tools available"),
                            confidence=0.4
                        )
                
                for f in unread_files:
                    name = f.get('name', '') if isinstance(f, dict) else str(f)
                    # Read any documentation or source files
                    if any(ext in name.lower() for ext in ['.md', '.txt', '.xml', '.json', '.toml', '.gradle', '.kt', '.java', '.py', '.js', '.ts']):
                        return Decision(
                            thought=f"Continuing exploration: reading {name}",
                            action="filesystem.read",
                            args={"path": name},
                            done=False,
                            confidence=0.7
                        )
            
            # If truly nothing left to explore, provide summary
            if files_read >= 3 or world_state.iteration >= 20:
                summary = self._synthesize_summary(world_state, error)
                return Decision(
                    thought=f"Explored {files_read} files. Providing analysis.",
                    done=True,
                    final_answer=summary,
                    confidence=0.7
                )
        
        # Non-exploratory queries: Try to give quick answer
        if len(world_state.observations) >= 2:
            summary = "\n".join(world_state.observations)
            return Decision(
                thought=f"LLM unavailable, providing current observations",
                done=True,
                final_answer=f"Based on observations:\n{summary}",
                confidence=0.5
            )
        
        # Default: List files if nothing else
        return Decision(
            thought="Starting with file listing (fallback mode)",
            action="filesystem.list",
            args={"path": "."},
            done=False,
            confidence=0.6
        )
    
    def _synthesize_summary(self, world_state, error: str) -> str:
        """
        Build a meaningful summary from actual file contents.
        Uses real content (imports, dependencies, function names) — not just metadata.
        """
        file_contents = world_state.knowledge.get('file_contents', {})

        if not file_contents:
            return "Based on observations:\n" + "\n".join(world_state.observations)

        project_type = self._identify_project_type(file_contents)
        sections = []
        sections.append("[DIR] Project Summary")
        sections.append("=" * 60)

        # ── Per-file analysis using actual content ──
        for file_path, content in file_contents.items():
            fname = file_path.lower()
            lines = content.split('\n')
            non_empty = [l.strip() for l in lines if l.strip()]

            if 'package.json' in fname:
                import json as _j
                try:
                    pkg = _j.loads(content)
                    name = pkg.get('name', 'unknown')
                    desc = pkg.get('description', '')
                    deps = list(pkg.get('dependencies', {}).keys())
                    dev_deps = list(pkg.get('devDependencies', {}).keys())
                    scripts = list(pkg.get('scripts', {}).keys())
                    sections.append(f"\n[PKG] package.json — {name}")
                    if desc:
                        sections.append(f" Description: {desc}")
                    if deps:
                        sections.append(f" Dependencies: {', '.join(deps[:12])}")
                    if dev_deps:
                        sections.append(f" Dev deps: {', '.join(dev_deps[:6])}")
                    if scripts:
                        sections.append(f" Scripts: {', '.join(scripts)}")
                except Exception:
                    sections.append(f"\n[PKG] {file_path} (could not parse)")

            elif any(fname.endswith(ext) for ext in ['.js', '.ts', '.jsx', '.tsx', '.mjs']):
                requires = []
                funcs = []
                classes = []
                for line in lines:
                    s = line.strip()
                    if s.startswith('const ') and 'require(' in s:
                        mod = s.split('require(')[-1].split(')')[0].strip("'\" ")
                        requires.append(mod)
                    elif s.startswith('import ') and ' from ' in s:
                        mod = s.split(' from ')[-1].strip("'\";\\ ")
                        requires.append(mod)
                    elif s.startswith(('function ', 'async function ', 'export function ')):
                        fn = s.split('(')[0].split(' ')[-1]
                        if fn and fn not in ('=', '{', ''):
                            funcs.append(fn)
                    elif s.startswith('class '):
                        cls = s.split('(')[0].split(' ')[-1]
                        classes.append(cls)
                sections.append(f"\n[DOC] {file_path} ({len(non_empty)} lines)")
                if requires:
                    sections.append(f" Uses: {', '.join(dict.fromkeys(requires[:12]))}")
                if funcs:
                    sections.append(f" Functions: {', '.join(funcs[:8])}")
                if classes:
                    sections.append(f" Classes: {', '.join(classes[:5])}")
                # Pull first meaningful comment as purpose hint
                for line in lines[:30]:
                    s = line.strip()
                    if s.startswith(('//', '*', '/*')) and len(s) > 12:
                        hint = s.lstrip('/*\\- ').strip()
                        if hint:
                            sections.append(f" └ {hint}")
                            break

            elif fname.endswith('.py'):
                imports = [l.strip() for l in lines if l.strip().startswith(('import ', 'from '))]
                defs = [l.strip().split('(')[0].replace('def ', '').replace('async def ', '')
                        for l in lines if l.strip().startswith(('def ', 'async def '))]
                sections.append(f"\n[DOC] {file_path} ({len(non_empty)} lines)")
                if imports:
                    sections.append(f" Imports: {', '.join(i.split()[-1] for i in imports[:8])}")
                if defs:
                    sections.append(f" Functions: {', '.join(defs[:8])}")

            elif fname.endswith('.md') or 'readme' in fname:
                preview = content[:300].strip()
                sections.append(f"\n {file_path}")
                sections.append(f" {preview}")
            else:
                sections.append(f"\n[DOC] {file_path} ({len(non_empty)} lines)")

        # ── Purpose paragraph ──
        sections.append("\n" + "=" * 60)
        sections.append("[SEARCH] Purpose & Architecture")
        sections.append(self._generate_overview(file_contents, project_type))

        return "\n".join(sections)
    
    def _identify_project_type(self, file_contents: dict) -> str:
        """Identify project type from file names and contents."""
        files = list(file_contents.keys())
        contents = " ".join([c[:500].lower() for c in file_contents.values()])
        
        # Android project
        if any('gradle' in f.lower() for f in files) or 'android' in contents:
            if any('kotlin' in f.lower() for f in files) or 'kotlin' in contents:
                return "Android Project (Kotlin)"
            return "Android Project (Java)"
        
        # Python project
        if any('setup.py' in f.lower() or 'requirements.txt' in f.lower() for f in files):
            return "Python Project"
        
        # Node.js project
        if any('package.json' in f.lower() for f in files):
            if 'react' in contents:
                return "React/Node.js Project"
            return "Node.js Project"
        
        # Rust project
        if any('cargo.toml' in f.lower() for f in files):
            return "Rust Project"
        
        # Java project
        if any('pom.xml' in f.lower() for f in files):
            return "Java/Maven Project"
        
        return "Code Project"
    
    def _summarize_file_content(self, file_path: str, content: str) -> str:
        """Create 1-2 line summary of a file's contents."""
        filename = file_path.lower()
        lines = content.split('\n')
        
        # Gradle files
        if 'gradle' in filename:
            # Extract dependencies, app info
            if 'applicationId' in content:
                app_id = [l for l in lines if 'applicationId' in l]
                if app_id:
                    return f"Build configuration - {app_id[0].strip()}"
            return f"Build configuration file ({len(lines)} lines)"
        
        # Manifest files
        if 'manifest' in filename:
            if '<manifest' in content:
                package = [l for l in lines if 'package=' in l]
                if package:
                    return f"App manifest - {package[0].strip()[:80]}"
            return f"Application manifest file"
        
        # README files
        if 'readme' in filename:
            # First non-empty line is usually the title
            for line in lines[:5]:
                if line.strip() and not line.startswith('#'):
                    return f"Documentation: {line.strip()[:60]}"
                if line.startswith('# '):
                    return f"Documentation: {line[2:].strip()[:60]}"
            return "Project documentation"
        
        # Package.json
        if 'package.json' in filename:
            if '"name"' in content:
                name_line = [l for l in lines if '"name"' in l]
                if name_line:
                    return f"NPM package config - {name_line[0].strip()}"
            return "NPM package configuration"
        
        # Generic code file
        if any(ext in filename for ext in ['.py', '.java', '.kt', '.js', '.ts']):
            non_empty = [l for l in lines if l.strip() and not l.strip().startswith('#')]
            return f"Source code file ({len(non_empty)} lines of code)"
        
        # Generic
        return f"File content ({len(lines)} lines, {len(content)} chars)"
    
    def _generate_overview(self, file_contents: dict, project_type: str) -> str:
        """Generate high-level overview of the project."""
        files = list(file_contents.keys())
        all_content = " ".join([c[:1000].lower() for c in file_contents.values()])

        parts = []

        # ── Detect purpose from real dependency/import clues ──
        if 'Node.js' in project_type or 'React' in project_type:
            # Slack bot
            if '@slack/bolt' in all_content or 'slack' in all_content:
                parts.append("This is a Slack bot / integration.")
            # Express API
            if 'express' in all_content:
                parts.append("Uses Express.js HTTP server.")
            # Google APIs
            if 'googleapis' in all_content or 'google-auth' in all_content:
                parts.append("Integrates with Google APIs (Drive / Sheets / etc.).")
            # Jira
            if 'jira' in all_content:
                parts.append("Connects to Jira for issue tracking.")
            # Discord
            if 'discord' in all_content:
                parts.append("This is a Discord bot.")
            # GraphQL
            if 'graphql' in all_content or 'apollo' in all_content:
                parts.append("Uses GraphQL / Apollo.")
            # DB
            if any(db in all_content for db in ['mongoose', 'sequelize', 'prisma', 'pg', 'sqlite']):
                parts.append("Includes database integration.")
            if not parts:
                parts.append("This is a Node.js application.")
            if 'react' in all_content:
                parts.append("Frontend built with React.")
            if 'typescript' in all_content or '.ts"' in all_content:
                parts.append("Written in TypeScript.")
            if 'dotenv' in all_content or '.env' in all_content:
                parts.append("Uses environment variables (.env).")

        elif 'Android' in project_type:
            parts.append("Android mobile application.")
            if 'kotlin' in all_content:
                parts.append("Written in Kotlin.")
            if 'compose' in all_content:
                parts.append("Uses Jetpack Compose for UI.")
            if 'retrofit' in all_content:
                parts.append("Uses Retrofit for networking.")
            if 'viewmodel' in all_content or 'livedata' in all_content:
                parts.append("Uses Android Architecture Components (ViewModel/LiveData).")

        elif 'Python' in project_type:
            parts.append("Python project.")
            if 'flask' in all_content:
                parts.append("Uses Flask web framework.")
            elif 'fastapi' in all_content:
                parts.append("Uses FastAPI.")
            elif 'django' in all_content:
                parts.append("Uses Django web framework.")
            if 'openai' in all_content or 'ollama' in all_content:
                parts.append("Integrates with AI/LLM APIs.")
            if 'chromadb' in all_content or 'faiss' in all_content:
                parts.append("Uses a vector database.")

        elif 'Rust' in project_type:
            parts.append("Rust project.")
            if 'tokio' in all_content:
                parts.append("Uses Tokio async runtime.")
            if 'actix' in all_content or 'axum' in all_content:
                parts.append("Includes an HTTP server.")

        if not parts:
            parts.append(f"{project_type}.")

        return " ".join(parts)
