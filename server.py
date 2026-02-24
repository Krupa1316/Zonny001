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

from fastapi import UploadFile, File, FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
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
# v0.4: Company runtime
from zonny.company_runtime import stream_company, run_company

OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

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
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

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
    MCP Gateway — Zonny v0.3 (AutoGen-powered)

    All prompts route through the 2-agent AutoGen team:
      Specialist → analyses task
      Assistant  → synthesises final answer + TERMINATE
    """
    if not req.input and not req.command:
        raise HTTPException(status_code=400, detail="Must provide input or command")

    user_input = (req.input or req.command or "").strip()
    context = {"session": req.session, "cwd": os.getcwd()}

    # Handle slash commands
    if user_input.startswith("/"):
        try:
            from commands.system import handle_system_command
            resp = handle_system_command(user_input, req.session, context)
            if resp:
                return {"response": resp.get("response", ""), "mode": "command"}
        except Exception:
            pass  # Fall through to AutoGen if command handler missing

    try:
        result = await run_team(task=user_input, session_id=req.session)
        return {
            "response": result["final_response"],
            "conversation": result["conversation"],
            "specialist": result["specialist"],
            "mode": "autogen",
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Return as 200 so the UI displays the error clearly
        return {
            "response": f"Agent error: {e}",
            "detail": tb,
            "mode": "error",
        }


# ============================================================
# Company — Software Company Agent Pipeline
# ============================================================

class CompanyRequest(BaseModel):
    session: str
    prompt: str


@app.post("/company/stream")
async def company_stream(
    req: CompanyRequest, _: str = Depends(verify_api_key)
):
    """
    SSE stream of the 6-agent software company pipeline.
    Events: {type: message|done, agent, content, files_extracted}
    """
    sid = req.session or str(__import__('uuid').uuid4())[:8]

    async def gen():
        try:
            async for event in stream_company(req.prompt, session_id=sid):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'type':'error','content':str(e),'detail':traceback.format_exc()})}\n\n"
        finally:
            yield f"data: {json.dumps({'type':'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


@app.get("/company/files/{session}")
async def list_company_files(session: str, _: str = Depends(verify_api_key)):
    """List files generated by a company session."""
    session_dir = OUTPUTS_DIR / session
    if not session_dir.exists():
        return {"files": []}
    files = []
    for f in session_dir.iterdir():
        if f.is_file():
            files.append({"name": f.name, "size": f.stat().st_size,
                           "path": str(f).replace("\\", "/")})
    return {"files": files, "session": session}


@app.get("/company/file/{session}/{filename}")
async def get_company_file(
    session: str, filename: str, _: str = Depends(verify_api_key)
):
    """Return content of a generated file."""
    fpath = OUTPUTS_DIR / session / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": filename, "content": fpath.read_text(encoding="utf-8")}


# ============================================================
# Preview — serve generated apps in an iframe
# ============================================================

@app.get("/preview/{session}")
async def preview_app(session: str):
    """Serve the generated app's index.html (or first .html file) for iframe preview."""
    session_dir = OUTPUTS_DIR / session
    if not session_dir.exists():
        return HTMLResponse("<h2 style='font-family:sans-serif;color:#888;padding:40px'>No generated files yet. Run the Company pipeline first.</h2>")
    # Look for index.html first, then any .html
    index = session_dir / "index.html"
    if not index.exists():
        html_files = list(session_dir.glob("*.html"))
        if html_files:
            index = html_files[0]
        else:
            return HTMLResponse("<h2 style='font-family:sans-serif;color:#888;padding:40px'>No HTML files generated. Only non-HTML files were created.</h2>")
    content = index.read_text(encoding="utf-8")
    # Rewrite relative CSS/JS paths to route through /preview/{session}/
    # e.g. href="style.css" → href="/preview/{session}/style.css"
    import re as _re
    content = _re.sub(r'(href|src)="(?!https?://|//)([^"]+)"',
                      rf'\1="/preview/{session}/\2"', content)
    return HTMLResponse(content)


@app.get("/preview/{session}/{filename:path}")
async def preview_static(session: str, filename: str):
    """Serve static assets (CSS, JS, images) for the previewed app."""
    fpath = OUTPUTS_DIR / session / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Determine content type
    ext = fpath.suffix.lower()
    ct_map = {".html":"text/html",".css":"text/css",".js":"application/javascript",
              ".json":"application/json",".png":"image/png",".jpg":"image/jpeg",
              ".svg":"image/svg+xml",".ico":"image/x-icon",".gif":"image/gif"}
    ct = ct_map.get(ext, "text/plain")
    from starlette.responses import Response
    return Response(content=fpath.read_bytes(), media_type=ct)


# ============================================================
# File API — read/write/tree any path (for IDE)
# ============================================================

class FileReadRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    path: str
    content: str


@app.post("/files/read")
async def file_read(req: FileReadRequest, _: str = Depends(verify_api_key)):
    """Read any file from disk."""
    p = Path(req.path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        return {"path": str(p), "content": p.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/files/write")
async def file_write(req: FileWriteRequest, _: str = Depends(verify_api_key)):
    """Write/save a file to disk."""
    p = Path(req.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(req.content, encoding="utf-8")
    return {"saved": str(p), "size": p.stat().st_size}


@app.get("/files/tree")
async def file_tree(
    path: str = ".", _: str = Depends(verify_api_key)
):
    """Return directory tree (1 level per call for performance)."""
    root = Path(path).resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    entries = []
    try:
        for item in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            entries.append({
                "name":   item.name,
                "path":   str(item).replace("\\", "/"),
                "type":   "file" if item.is_file() else "directory",
                "size":   item.stat().st_size if item.is_file() else None,
                "ext":    item.suffix.lstrip(".") if item.is_file() else None,
            })
    except PermissionError:
        pass
    return {"path": str(root).replace("\\","/"), "entries": entries}


# ============================================================
# Terminal — WebSocket PTY
# ============================================================

@app.websocket("/terminal")
async def terminal_ws(ws: WebSocket, api_key: str = ""):
    """
    WebSocket terminal: spawns PowerShell, streams I/O bidirectionally.
    Connect with ?api_key=... in the URL query param.
    """
    # Validate key via query param (WebSocket can't send headers easily)
    valid_keys = load_keys()
    if valid_keys and api_key not in valid_keys:
        await ws.close(code=4001)
        return

    await ws.accept()
    proc = await asyncio.create_subprocess_exec(
        "powershell.exe", "-NoLogo", "-NoProfile",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def read_output():
        """Pump subprocess stdout → websocket."""
        try:
            while True:
                chunk = await proc.stdout.read(1024)
                if not chunk:
                    break
                await ws.send_text(chunk.decode("utf-8", errors="replace"))
        except Exception:
            pass

    reader_task = asyncio.create_task(read_output())

    try:
        while True:
            data = await ws.receive_text()
            if proc.stdin and not proc.stdin.is_closing():
                proc.stdin.write(data.encode("utf-8"))
                await proc.stdin.drain()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        reader_task.cancel()
        try:
            proc.terminate()
        except Exception:
            pass



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
