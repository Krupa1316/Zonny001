from fastapi import UploadFile, File, FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from pathlib import Path
from pypdf import PdfReader
import requests, json, uuid, os

from zonny.memory import store_message, retrieve_memory, store_text_blocks
from orchestrator import orchestrate

# Slice D: Initialize tools (triggers registration)
import tools

# Slice B: Initialize agents (triggers registration)
import agents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_HEADER = APIKeyHeader(name="Authorization")
KEY_FILE = Path("key.json")

def load_keys():
    if not KEY_FILE.exists():
        return []
    c = KEY_FILE.read_text().strip()
    return json.loads(c) if c else []

def verify_api_key(api_key: str = Depends(API_KEY_HEADER)):
    if api_key not in load_keys():
        raise HTTPException(status_code=401, detail="Invalid API key")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    conversation_id: str = "default"
    document_id: str | None = None

# Slice A: MCP Request Model (Zonny Protocol v1)
class MCPRequest(BaseModel):
    session: str
    input: str | None = None
    command: str | None = None


# ============================================================
# Slice A: MCP Gateway Endpoint (Zonny Protocol v1)
# ============================================================

@app.post("/mcp")
def mcp_gateway(req: MCPRequest, _: str = Depends(verify_api_key)):
    """
    MCP Gateway - The single endpoint for Zonny CLI.
    
    PHASE 2 Architecture (Dual Mode):
    
    MODE 1 - Router (simple queries):
      CLI → Semantic Router → Intent → Dispatcher → Result
      
    MODE 2 - Planner (complex tasks):
      CLI → Planner → Execution Plan → Executor → Reflector → Result
    
    Automatically selects mode based on task complexity.
    
    Phase 1: Router = Fast single-step (natural language → tool)
    Phase 2: Planner = Multi-step workflows (task → plan → execute → verify)
    """
    from zonny.semantic_router import route
    from zonny.dispatcher import dispatch
    from zonny.planner import plan, is_complex_task
    from zonny.executor import execute_plan, get_final_result
    from zonny.reflector import reflect
    from tools.workspace import scan_workspace
    from commands.system import handle_system_command
    
    # Validate payload
    if not req.input and not req.command:
        raise HTTPException(status_code=400, detail="Must provide input or command")
    
    # Build context
    workspace_context = scan_workspace()
    context = {
        "session": req.session,
        "cwd": os.getcwd(),
        "files": workspace_context.get('files', []),
        "directories": workspace_context.get('directories', []),
        "workspace": workspace_context.get('workspace', 'unknown')
    }
    
    user_input = req.input or req.command or ""
    
    # Handle legacy system commands (backwards compatibility)
    if user_input.startswith('/'):
        command_response = handle_system_command(user_input, req.session, context)
        if command_response:
            return {
                "response": command_response.get('response', ''),
                "action": command_response.get('action'),
                "context": context,
                "mode": "command"
            }
    
    # NEW: Intelligent mode selection
    try:
        # Decide: Router (Phase 1) or Planner (Phase 2)?
        use_planner = is_complex_task(user_input)
        
        if use_planner:
            # ═══════════════════════════════════════════════════════
            # PHASE 2 MODE: Multi-Step Planning
            # ═══════════════════════════════════════════════════════
            
            # Step 1: Plan - Break task into steps
            plan_obj = plan(user_input, context)
            
            # Step 2: Execute - Run each step
            execution = execute_plan(plan_obj, context, verbose=False)
            
            # Step 3: Reflect - Verify completion
            reflection = reflect(plan_obj["goal"], execution, context)
            
            # Step 4: Get result
            result = get_final_result(execution)
            
            # Add reflection status to response
            if not reflection.get("done"):
                result += f"\n\n⚠️  Task may be incomplete: {reflection.get('reason')}"
                if reflection.get("next_action"):
                    result += f"\n💡 Suggestion: {reflection['next_action']}"
            
            return {
                "response": result,
                "mode": "planner",
                "plan": plan_obj,
                "execution": {
                    "steps_completed": execution["steps_completed"],
                    "total_steps": execution["total_steps"],
                    "success": execution["success"]
                },
                "reflection": reflection,
                "context": context
            }
        
        else:
            # ═══════════════════════════════════════════════════════
            # PHASE 1 MODE: Direct Routing (unchanged)
            # ═══════════════════════════════════════════════════════
            
            # Step 1: Route input → JSON intent (LLM-based)
            intent = route(user_input, context)
            
            # Step 2: Dispatch intent → Result
            result = dispatch(intent, context)
            
            # Step 3: Return response
            return {
                "response": result,
                "mode": "router",
                "intent": intent,  # Include intent for transparency
                "context": context
            }
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {
            "response": f"❌ System error: {e}\n\nDetails:\n{error_detail}",
            "mode": "error",
            "context": context
        }


# ============================================================
# Legacy Endpoints (Pre-Slice A)
# ============================================================

@app.post("/v1/chat/completions")
def chat(req: ChatRequest, _: str = Depends(verify_api_key)):
    """
    🧠 Orchestrator-based chat endpoint
    
    Flow:
    1. Orchestrator decides which agents to use
    2. Agents gather specialized context
    3. Orchestrator synthesizes final response
    """
    
    user_text = req.messages[-1].content
    
    # 🎯 Use orchestrator instead of simple RAG
    reply, debug_info = orchestrate(
        user_message=user_text,
        conversation_id=req.conversation_id,
        document_id=req.document_id
    )
    
    # Store in memory
    store_message(user_text, "user", req.conversation_id)
    store_message(reply, "assistant", req.conversation_id)
    
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": reply
            }
        }],
        "debug": debug_info  # Optional: for transparency
    }

@app.post("/v1/upload")
def upload(
    file: UploadFile = File(...),
    conversation_id: str = "default",
    _: str = Depends(verify_api_key)
):

    document_id = str(uuid.uuid4())
    content = ""

    if file.filename.endswith(".pdf"):
        reader = PdfReader(file.file)
        for p in reader.pages:
            t = p.extract_text()
            if t:
                content += t + "\n"
    else:
        content = file.file.read().decode()

    store_text_blocks(
        content,
        file.filename,
        "document",
        document_id,
        conversation_id
    )

    return {
        "status": "uploaded",
        "filename": file.filename,
        "document_id": document_id
    }


# ============================================================
# Phase 4: Agent Management Endpoints (Gemini-style)
# ============================================================

@app.get("/agents")
def list_agents(_: str = Depends(verify_api_key)):
    """
    List all agents with their enabled status.
    
    Similar to Gemini CLI's /agents list
    """
    return {
        "agents": registry.list_agents(),
        "total": len(registry.manifests),
        "enabled": len(registry.enabled_agents)
    }


@app.post("/agents/{name}/enable")
def enable_agent(name: str, _: str = Depends(verify_api_key)):
    """
    Enable a specific agent.
    
    Similar to Gemini CLI's /agents enable
    """
    if name not in registry.manifests:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    
    registry.enable_agent(name)
    return {
        "status": "enabled",
        "agent": name
    }


@app.post("/agents/{name}/disable")
def disable_agent(name: str, _: str = Depends(verify_api_key)):
    """
    Disable a specific agent.
    
    Similar to Gemini CLI's /agents disable
    """
    if name not in registry.manifests:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    
    registry.disable_agent(name)
    return {
        "status": "disabled",
        "agent": name
    }


@app.post("/agents/refresh")
def refresh_agents(_: str = Depends(verify_api_key)):
    """
    Reload all agent manifests from disk.
    
    Similar to Gemini CLI's /agents refresh
    Allows hot-reload without server restart.
    """
    try:
        count = registry.load_manifests("agents/manifests")
        return {
            "status": "reloaded",
            "count": count,
            "enabled": len(registry.enabled_agents)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload manifests: {e}")


@app.get("/agents/{name}")
def get_agent_details(name: str, _: str = Depends(verify_api_key)):
    """
    Get detailed information about a specific agent.
    """
    manifest = registry.get_manifest(name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    
    return {
        "name": name,
        "enabled": registry.is_agent_enabled(name),
        "manifest": manifest
    }

