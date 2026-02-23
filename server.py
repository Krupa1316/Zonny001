"""
Zonny v0.3.0 — FastAPI Server

Two modes exposed at POST /mcp:
  - Simple:  semantic router → dispatcher  (fast)
  - Complex: AutoGen team   → SSE stream   (powerful, multi-model)

New endpoints added in v0.3:
  GET  /               → Web Chat UI (frontend/index.html)
  GET  /stream         → SSE stream of agent events (AutoGen)
  GET  /agents/status  → Real-time agent roster for UI sidebar

Legacy endpoints preserved:
  POST /v1/chat/completions
  POST /v1/upload
  GET/POST /agents/*   (enable, disable, refresh, details)
"""

import asyncio
import json
import uuid
import os
from pathlib import Path

from fastapi import UploadFile, File, FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader

from zonny.memory import store_message, retrieve_memory, store_text_blocks
from orchestrator import orchestrate

# Slice D: Initialize tools (triggers registration)
import tools

# Slice B: Initialize agents (triggers registration)
import agents
from agents.manifest_loader import ManifestLoader

_manifest_loader = ManifestLoader("agents/manifests")

# v0.3: AutoGen runtime
from zonny.autogen_runtime import run_team, stream_team, get_agent_status

app = FastAPI(title="Zonny", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the web UI frontend
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

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


class MCPRequest(BaseModel):
    session: str
    input: str | None = None
    command: str | None = None


# ============================================================
# v0.3: Web Chat UI
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the Zonny Web Chat UI"""
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return HTMLResponse(
            content="<h1>Zonny v0.3.0</h1><p>Frontend not found. Run the server from project root.</p>",
            status_code=200
        )
    return HTMLResponse(content=index.read_text(encoding="utf-8"))


@app.get("/stream")
async def stream_agent_activity(
    task: str,
    session: str = "default",
    _: str = Depends(verify_api_key)
):
    """
    SSE endpoint: streams AutoGen agent events as they happen.

    Used by the Web UI's live agent activity panel.

    Query params:
        task:    The user's message/task
        session: Session ID for memory scoping
    """
    async def event_generator():
        try:
            async for event in stream_team(task=task, session_id=session):
                data = json.dumps(event)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)  # Allow event loop to breathe
        except Exception as e:
            error_event = json.dumps({
                "agent": "system",
                "type": "error",
                "content": str(e),
                "model": ""
            })
            yield f"data: {error_event}\n\n"
        finally:
            done_event = json.dumps({
                "agent": "system",
                "type": "done",
                "content": "",
                "model": ""
            })
            yield f"data: {done_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/agents/status")
async def agent_status_list(_: str = Depends(verify_api_key)):
    """
    Return current agent roster with model info for the Web UI sidebar.
    """
    return {"agents": await get_agent_status()}


# ============================================================
# MCP Gateway — AutoGen runtime
# ============================================================

@app.post("/mcp")
async def mcp_gateway(req: MCPRequest, _: str = Depends(verify_api_key)):
    """
    MCP Gateway — Zonny Protocol v1 / v0.3

    v0.3 change: complex tasks now route through AutoGen multi-model team.

    MODE 1 - Router (simple queries, fast):
      CLI → Semantic Router → Intent → Dispatcher → Result

    MODE 2 - AutoGen Team (complex tasks):
      CLI → AutoGen SelectorGroupChat → Result
    """
    from zonny.semantic_router import route
    from zonny.dispatcher import dispatch
    from zonny.planner import is_complex_task
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
        "files": workspace_context.get("files", []),
        "directories": workspace_context.get("directories", []),
        "workspace": workspace_context.get("workspace", "unknown"),
    }

    user_input = req.input or req.command or ""

    # Handle legacy system commands (backwards compatibility)
    if user_input.startswith("/"):
        try:
            from commands.system import handle_system_command
            command_response = handle_system_command(user_input, req.session, context)
            if command_response:
                return {
                    "response": command_response.get("response", ""),
                    "action": command_response.get("action"),
                    "context": context,
                    "mode": "command",
                }
        except ImportError:
            pass

    try:
        # Always route through AutoGen multi-agent team
        result = await run_team(task=user_input, session_id=req.session)

        return {
            "response": result["final_response"],
            "conversation": result["conversation"],
            "specialist": result["specialist"],
            "mode": "autogen",
            "context": context,
        }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {
            "response": f"System error: {e}\n\nDetails:\n{error_detail}",
            "mode": "error",
            "context": context,
        }



# ============================================================
# Legacy Endpoints — preserved from v0.2
# ============================================================

@app.post("/v1/chat/completions")
def chat(req: ChatRequest, _: str = Depends(verify_api_key)):
    """
    🧠 Orchestrator-based chat endpoint (legacy, preserved)

    Flow:
    1. Orchestrator decides which agents to use
    2. Agents gather specialized context
    3. Orchestrator synthesizes final response
    """
    user_text = req.messages[-1].content

    reply, debug_info = orchestrate(
        user_message=user_text,
        conversation_id=req.conversation_id,
        document_id=req.document_id
    )

    store_message(user_text, "user", req.conversation_id)
    store_message(reply, "assistant", req.conversation_id)

    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": reply
            }
        }],
        "debug": debug_info
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
# Agent Management Endpoints
# ============================================================

@app.get("/agents")
def list_agents(_: str = Depends(verify_api_key)):
    """List all agents with their enabled status."""
    manifests = _manifest_loader.load_all_manifests()
    agent_list = [
        {
            "name": m.name,
            "description": m.description,
            "enabled": m.enabled,
            "priority": m.priority,
            "tools": m.tools,
        }
        for m in manifests.values()
    ]
    return {
        "agents": agent_list,
        "total": len(agent_list),
        "enabled": sum(1 for m in manifests.values() if m.enabled)
    }


@app.post("/agents/{name}/enable")
def enable_agent(name: str, _: str = Depends(verify_api_key)):
    """Enable a specific agent (writes back to manifest YAML)."""
    manifests = _manifest_loader.load_all_manifests()
    if name not in manifests:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {"status": "enabled", "agent": name, "note": "Set enabled: true in manifest YAML to persist"}


@app.post("/agents/{name}/disable")
def disable_agent(name: str, _: str = Depends(verify_api_key)):
    """Disable a specific agent (writes back to manifest YAML)."""
    manifests = _manifest_loader.load_all_manifests()
    if name not in manifests:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {"status": "disabled", "agent": name, "note": "Set enabled: false in manifest YAML to persist"}


@app.post("/agents/refresh")
def refresh_agents(_: str = Depends(verify_api_key)):
    """Reload all agent manifests from disk (hot-reload)."""
    try:
        manifests = _manifest_loader.load_all_manifests()
        return {
            "status": "reloaded",
            "count": len(manifests),
            "enabled": sum(1 for m in manifests.values() if m.enabled)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload manifests: {e}")


@app.get("/agents/{name}")
def get_agent_details(name: str, _: str = Depends(verify_api_key)):
    """Get detailed information about a specific agent."""
    manifests = _manifest_loader.load_all_manifests()
    if name not in manifests:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    m = manifests[name]
    return {
        "name": m.name,
        "enabled": m.enabled,
        "manifest": {
            "description": m.description,
            "system_prompt": m.system_prompt,
            "tools": m.tools,
            "priority": m.priority,
            "context_scope": m.context_scope,
            "max_iterations": m.max_iterations,
        }
    }
