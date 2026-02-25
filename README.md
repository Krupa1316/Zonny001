# Zonny -- Local AI Development Platform

Zonny is an AI-powered development platform that runs entirely on your local machine. It uses locally-hosted language models to provide a multi-agent coding environment with a web-based IDE, a software company simulator that builds applications from natural language prompts, and an automatic error detection and repair system.

Everything runs on your hardware. No cloud APIs, no subscriptions, no data leaving your machine.

---

## Table of Contents

- [What is Zonny?](#what-is-zonny)
- [Key Concepts for Beginners](#key-concepts-for-beginners)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Starting the Server](#starting-the-server)
- [Using the Web Interface](#using-the-web-interface)
- [Using the CLI](#using-the-cli)
- [Agent Architecture](#agent-architecture)
- [REST API Reference](#rest-api-reference)
- [MCP Integration](#mcp-integration)
- [Permission Modes](#permission-modes)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Diagnostics](#diagnostics)
- [Contributing](#contributing)
- [Tech Stack](#tech-stack)
- [License](#license)

---

## What is Zonny?

Zonny is a platform where AI agents collaborate to help you write software. When you type a prompt like "Build a Pomodoro timer app," six specialised AI agents work together -- a CEO writes the requirements, an architect designs the system, frontend and backend engineers write the code, a QA engineer tests it, and a reviewer signs off. The generated application is immediately previewed in your browser, and if it has errors, the agents automatically detect and fix them.

Zonny also provides:

- A full web-based code editor (powered by the same engine as VS Code)
- An integrated terminal for running commands
- A multi-agent chat system for asking questions about code, documents, or general topics
- Persistent memory so the AI remembers your previous conversations

---

## Key Concepts for Beginners

If you are new to AI engineering, here are the core ideas behind Zonny:

### What is a Language Model (LLM)?

A language model is a type of AI that can read and generate text. It can understand instructions, answer questions, write code, and have conversations. Examples include GPT, Claude, and Gemini. Zonny uses **Ollama** to run these models directly on your computer instead of sending requests to the cloud.

### What is Ollama?

Ollama is a free, open-source tool that downloads and runs language models on your local machine. Think of it as a local server for AI models. Zonny sends prompts to Ollama and receives responses -- all without an internet connection.

### What is an AI Agent?

An AI agent is a program that uses a language model to take actions, not just generate text. For example, instead of just saying "you should create a file called main.py," an agent actually creates the file. Zonny has multiple agents, each specialised for different tasks.

### What is a Multi-Agent System?

Instead of one AI doing everything, Zonny uses teams of agents that pass work between each other. The "Software Company" mode uses six agents in a pipeline, while the "Chat" mode uses a router agent that picks the best specialist for your question.

### What is ReAct?

ReAct (Reason + Act) is a pattern where the AI thinks about what to do, takes an action, observes the result, and then thinks again. This loop continues until the task is complete. It is more reliable than a single-shot "generate all the code at once" approach.

---

## System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| Operating System | Windows 10, macOS 12, Ubuntu 20.04 | Windows 11, macOS 14, Ubuntu 22.04 |
| Python | 3.10 or higher | 3.12 |
| RAM | 8 GB | 16 GB or more |
| Disk Space | 10 GB (for models) | 40 GB (for larger coding models) |
| GPU | Not required | NVIDIA GPU with 8+ GB VRAM speeds up inference |

### Required Software

1. **Python 3.10+** -- Download from [python.org](https://www.python.org/downloads/)
2. **Ollama** -- Download from [ollama.com](https://ollama.com)
3. **Git** (optional) -- Download from [git-scm.com](https://git-scm.com)

---

## Installation

Follow these steps in order. Each step must complete successfully before moving to the next.

### Step 1: Install Ollama and Download Models

After installing Ollama from [ollama.com](https://ollama.com), open a terminal and run:

```bash
# Download the default planning/reasoning model (small, fast)
ollama pull nemotron-3-nano:latest

# Download the coding model (large, powerful -- used by the Software Company)
ollama pull deepseek-coder:33b
```

The first model is about 2 GB. The second is about 19 GB. Both are downloaded once and cached locally.

To verify Ollama is working:

```bash
ollama list
```

You should see both models listed.

### Step 2: Clone the Repository

```bash
git clone https://github.com/Krupa1316/Zonny001.git
cd Zonny001
```

Or download and extract the ZIP file from the repository page.

### Step 3: Create a Virtual Environment

A virtual environment keeps Zonny's dependencies separate from your system Python.

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt after activation.

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, ChromaDB, sentence-transformers, and other required packages. It may take a few minutes on the first run.

### Step 5: Install Zonny as a Package (Optional)

This step makes the `zonny`, `zonny-server`, and `zonny-mcp` commands available system-wide:

```bash
pip install -e .
```

### Step 6: Generate an API Key

The server requires an API key for authentication:

```bash
python create_key.py
```

This creates a `key.json` file with a key in the format `sk-local-<hex>`. Keep this key -- you will need it when using the API or web interface.

---

## Starting the Server

Make sure Ollama is running first. If it is not running, start it:

```bash
ollama serve
```

Then start the Zonny server:

**Windows (PowerShell):**
```powershell
venv\Scripts\uvicorn.exe server:app --host 0.0.0.0 --port 8000
```

**macOS / Linux:**
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

The server will start and print output like:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open your browser and go to **http://localhost:8000** to access the web interface.

---

## Using the Web Interface

The web interface has five tabs. Here is what each one does and how to use it.

### Chat Tab

This is a conversation interface where you can ask questions and get answers from the AI agents.

**How to use:**
1. Type a message in the input box at the bottom
2. Press Enter or click Send
3. The system routes your question to the best specialist agent (code, documents, memory, or general)
4. The specialist analyses your question, then an assistant agent synthesises the final response

**Example prompts:**
- "Explain what this project does"
- "Read server.py and summarise the endpoints"
- "Write a Python function that validates email addresses"

The left sidebar shows the available agents and their assigned models. The right sidebar shows details about each agent's activity.

### Agent Log Tab

This tab shows the full internal conversation between agents. When you send a message in the Chat tab, you can switch to Agent Log to see how the router picked a specialist and how the agents worked together to produce the answer.

This is useful for understanding how the multi-agent system works and for debugging when responses are not what you expected.

### IDE Tab

A full code editor and terminal, similar to VS Code, running in your browser.

**Components:**
- **File Explorer** (left panel) -- Browse directories, click files to open them
- **Editor** (main panel) -- Syntax-highlighted code editor with multiple tabs. Supports all common languages (Python, JavaScript, HTML, CSS, JSON, YAML, etc.)
- **Terminal** (bottom panel) -- A real PowerShell (Windows) or Bash (Linux/macOS) terminal

**How to use:**
1. The file explorer defaults to the `outputs/` directory where generated apps are saved
2. Click any file to open it in the editor
3. Edit the code directly
4. Press Ctrl+S (or Cmd+S on macOS) to save
5. Use the terminal to run commands like `python main.py` or `npm start`

### Company Tab

This is the Software Company simulator. You describe what you want to build, and six AI agents collaborate to create it.

**The six agents and their roles:**

| Agent | Role | Model |
|-------|------|-------|
| CEO | Writes a Product Requirements Document (PRD) from your prompt | nemotron-3-nano |
| Architect | Designs the system architecture and file structure | nemotron-3-nano |
| Frontend Engineer | Writes HTML, CSS, and JavaScript code | deepseek-coder:33b |
| Backend Engineer | Writes Python, API, and server code | deepseek-coder:33b |
| QA Engineer | Reviews code for bugs and writes test cases | nemotron-3-nano |
| Reviewer | Final review, produces a ship report, signs off | nemotron-3-nano |

**How to use:**
1. Type a description of what you want to build (for example: "Build a todo list app with dark mode")
2. Click the Build button
3. Watch the pipeline execute -- each agent lights up as it works
4. Agent output streams in real time on the left panel
5. Generated files appear in the right panel
6. When the pipeline finishes, the Preview tab opens automatically

**Tips for better results:**
- Be specific in your prompt. "Build a todo list app with add, delete, and filter functionality, using HTML/CSS/JS" works better than "build an app."
- The agents work best for single-page web applications (HTML + CSS + JS)
- Generated files are saved to `outputs/<session-id>/`

### Preview Tab

This tab shows a live preview of the application built by the Company pipeline.

**Auto-Repair feature:**
When the preview loads, an error detection script monitors for JavaScript errors. If errors are found:

1. The status badge turns red and shows the number of errors detected
2. The system automatically sends the error messages and source code to repair agents
3. The Frontend and Backend engineers analyse the errors and produce fixed code
4. The preview reloads with the fixed code
5. This cycle repeats up to 3 times

**Status indicators:**
- Blue badge: "Loading preview" -- the preview is starting
- Green badge: "Running" -- the application loaded without errors
- Yellow badge: "Repairing (1/3)" -- agents are fixing errors (with a pulsing animation)
- Red badge: "Repair failed after 3 attempts" -- manual intervention needed

**Controls:**
- Refresh button: Reloads the preview and resets the repair counter
- New Tab button: Opens the generated application in a full browser tab

---

## Using the CLI

The command-line interface is an alternative to the web UI for terminal-focused workflows.

### Start the CLI

```bash
# If installed as a package:
zonny

# Or run directly:
python zonny.py
```

### Commands

| Command | Description |
|---------|-------------|
| `/agents` | List available agents and their capabilities |
| `/help` | Show the command reference |
| `/exit` | Exit Zonny |

### Example Session

```
> Zonny CLI v0.3
> Type a message or /help for commands.

you> What files are in the current directory?

[SEARCH] Routing to: codebase agent
[CODE] Scanning workspace...

The current directory contains:
  server.py (21 KB) -- FastAPI server
  memory.py (5.8 KB) -- ChromaDB memory
  orchestrator.py (8 KB) -- Agent orchestration
  ...

you> Read server.py and explain the endpoints

[CODE] Reading file: server.py
...
```

---

## Agent Architecture

Zonny uses two different agent architectures depending on the task.

### Chat Architecture (2-Agent Team)

Used for the Chat tab. A router picks the best specialist, then two agents collaborate:

```
User question
  --> Router selects specialist (code / docs / memory / general)
  --> Specialist agent analyses the question deeply
  --> Assistant agent synthesises a clean final answer
  --> Response returned to the user
```

The team uses `RoundRobinGroupChat` from Microsoft's AutoGen framework. Each agent runs in sequence, and the assistant agent marks the conversation as complete by saying "TERMINATE."

### Company Architecture (6-Agent Pipeline)

Used for the Company tab. Six agents run in a fixed sequence:

```
User prompt
  --> CEO: writes product requirements
  --> Architect: designs system and file structure
  --> Frontend Engineer: writes client-side code
  --> Backend Engineer: writes server-side code
  --> QA Engineer: reviews for bugs and edge cases
  --> Reviewer: final sign-off, outputs TERMINATE
```

Code files are extracted from agent output using marker patterns (`// FILE: filename.ext`) and saved to disk.

### Repair Architecture (2-Agent Fix)

Used when the preview detects errors. The Frontend and Backend engineers receive the current source files plus the error messages and produce corrected code.

---

## REST API Reference

Base URL: `http://localhost:8000`

All endpoints except `GET /` require an `Authorization` header with an API key.

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the web interface |
| POST | `/mcp` | Send a message to the multi-agent chat system |
| GET | `/stream` | SSE stream of agent activity in real time |
| GET | `/agents/status` | List all agents with their models and status |

### Company Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/company/stream` | Start a company pipeline (SSE stream) |
| POST | `/company/repair` | Start a repair cycle (SSE stream) |
| GET | `/company/files/{session}` | List files generated by a session |
| GET | `/company/files/{session}/{filename}` | Get a specific generated file |

### Preview Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/preview/{session}` | Serve the generated app's HTML (with error detection injected) |
| GET | `/preview/{session}/{filename}` | Serve static assets (CSS, JS, images) for the previewed app |

### File API (IDE)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/files/read` | Read a file from disk |
| POST | `/files/write` | Write/save a file to disk |
| GET | `/files/tree` | Browse directory contents |

### Terminal

| Protocol | Path | Description |
|----------|------|-------------|
| WebSocket | `/terminal` | Interactive terminal session (PowerShell or Bash) |

### Legacy Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | OpenAI-compatible chat endpoint |
| POST | `/v1/upload` | Upload and index a PDF document |

### Example: Sending a Chat Message

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: sk-local-your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"session": "my-session", "input": "What does server.py do?"}'
```

Response:
```json
{
  "response": "server.py is the main FastAPI server...",
  "session": "my-session"
}
```

### Example: Starting a Company Build

```bash
curl -X POST http://localhost:8000/company/stream \
  -H "Authorization: sk-local-your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"session": "build-001", "prompt": "Build a calculator app"}'
```

This returns a Server-Sent Events stream. Each event is a JSON object:
```
data: {"type": "message", "agent": "CEO_agent", "content": "...", "files_extracted": []}
data: {"type": "message", "agent": "frontend_engineer", "content": "...", "files_extracted": ["index.html"]}
data: {"type": "done", "ship_report": "...", "files": {"index.html": "..."}, "saved_paths": ["outputs/build-001/index.html"]}
```

---

## MCP Integration

Zonny includes a Model Context Protocol (MCP) server, allowing it to be used as a tool provider in Claude Desktop and other MCP-compatible clients.

### Claude Desktop Configuration

Add this to your Claude Desktop configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zonny": {
      "command": "python",
      "args": ["path/to/zonny/mcp_server.py"]
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `ask_agent` | Send a task to Zonny's ReAct agent |
| `read_file` | Read a file from the workspace |
| `list_files` | List files and directories |
| `search_files` | Search file contents by pattern |
| `write_file` | Write or modify a file |
| `run_command` | Execute a shell command (requires full permission mode) |
| `query_memory` | Search the vector memory store |

---

## Permission Modes

Zonny uses a three-tier permission system. Set the mode using the `ZONNY_MODE` environment variable:

```bash
# Windows PowerShell
$env:ZONNY_MODE = "dev"

# macOS / Linux
export ZONNY_MODE=dev
```

| Mode | Read Files | Write Files | Shell Commands | When to Use |
|------|-----------|-------------|----------------|-------------|
| `safe` | Yes | No | No | Exploring code, asking questions |
| `dev` | Yes | Yes (code files only) | No | Normal development (default) |
| `full` | Yes | Yes (all files) | Yes | Trusted environments only |

**Writable extensions in `dev` mode:**
```
.py .js .ts .jsx .tsx .html .css .scss
.json .yaml .yml .toml .md .txt .sh .env.example
```

**Always blocked (all modes):**
```
.exe .dll .so .bin .env .key .pem .cert .p12
```

---

## Configuration

### API Key

Generated by `python create_key.py`. Stored in `key.json`. Never commit this file to version control.

### Models

Models are configured in agent manifest files (`agents/manifests/*.yaml`). Each manifest specifies which Ollama model the agent uses:

```yaml
name: frontend_engineer
model: deepseek-coder:33b
system_prompt: |
  You are a frontend engineer...
```

To use a different model, change the `model` field in the manifest and make sure the model is pulled in Ollama.

### Ollama Host

By default, Zonny connects to Ollama at `http://localhost:11434`. To change this, set the `OLLAMA_HOST` environment variable:

```bash
# Windows PowerShell
$env:OLLAMA_HOST = "http://192.168.1.100:11434"

# macOS / Linux
export OLLAMA_HOST="http://192.168.1.100:11434"
```

---

## Project Structure

```
server.py                       Main FastAPI server (all HTTP and WebSocket endpoints)
orchestrator.py                 RAG + memory orchestration layer
memory.py                       ChromaDB vector memory interface
mcp_server.py                   MCP stdio server for Claude Desktop
zonny.py                        CLI entry point
zonny_status.py                 Diagnostic test suite (35 checks)
create_key.py                   API key generator
setup.py                        Package installer (pip install -e .)
requirements.txt                Python dependencies

zonny/                          Core runtime package
  autogen_runtime.py            Chat mode: 2-agent team (specialist + assistant)
  company_runtime.py            Company mode: 6-agent pipeline + auto-repair
  planner.py                    Decision engine (one action per step)
  dispatcher.py                 Secure OS interface (path safety, permissions)
  react_loop.py                 ReAct Think-Act-Observe engine
  reflector.py                  Answer quality evaluation
  semantic_router.py            Intent routing to agents
  agent.py                      Base agent implementation
  memory.py                     Vector memory interface
  tool_registry.py              Central tool registry
  executor.py                   Action execution
  router.py                     Task-level routing
  world.py                      Immutable world state
  cli.py                        Interactive terminal UI
  runtime.py                    Runtime configuration

agents/                         Agent definitions
  manifests/                    YAML agent configuration files
    assistant.yaml              Response synthesiser
    codebase.yaml               Code analysis agent
    document.yaml               Document Q&A agent
    generalist.yaml             General fallback agent
    memory.yaml                 Memory management agent
    ceo.yaml                    Company: product requirements
    architect.yaml              Company: system design
    frontend.yaml               Company: HTML/CSS/JS code
    backend.yaml                Company: Python/API code
    qa.yaml                     Company: testing and bugs
    reviewer.yaml               Company: final review
  agent_factory.py              Creates agents from manifests
  manifest_loader.py            Loads and validates YAML manifests
  base.py, code.py, docs.py,   Specialist agent implementations
  general.py, memory.py,
  planner_agent.py, registry.py,
  router.py

tools/                          Tool implementations
  fs.py                         Filesystem operations
  workspace.py                  Workspace scanning
  analyzer.py                   Code analysis
  shell.py                      Shell command execution
  memory_tool.py                Memory search/store
  vector_tool.py                Vector DB operations
  file_tool.py                  Extended file operations
  runner.py                     Command runner
  registry.py                   Tool registry

runtime/                        Runtime infrastructure
  engine.py                     Runtime engine
  subagent.py                   Sub-agent spawning
  registry.py                   Runtime service registry
  context.py                    Execution context
  base.py                       Base runtime class

frontend/                       Web interface (single-page application)
  index.html                    5-tab layout
  style.css                     Dark theme, grid layouts, animations
  app.js                        Editor, terminal, SSE streaming, auto-repair

commands/                       CLI command handlers
  system.py                     System commands (/help, /agents, etc.)

docs/                           Documentation
  runbook.md                    Operations runbook
  model-selection-playbook.md   Guide to choosing models
  token-optimization-guide.md   Token usage optimisation

outputs/                        Generated application files (per session)
```

---

## Diagnostics

Run the full test suite to verify your installation:

```bash
python zonny_status.py
```

This runs 35 automated checks across all system components:

- Ollama connectivity and model availability
- All Python package imports
- Tool registry integrity (17 tools)
- Agent manifest loading and validation
- Semantic router (intent classification)
- ReAct loop execution
- Dispatcher security (path traversal prevention, extension blocking)
- Permission mode enforcement
- Memory subsystem (ChromaDB + embeddings)
- FastAPI server health
- MCP protocol

Expected output:
```
 [OK] Passed : 35/35
 [FAIL] Failed : 0/35
 Score : 100%

 [DONE] All systems nominal. Zonny is ready.
```

If any checks fail, the output will tell you exactly what is wrong and how to fix it.

---

## Contributing

Contributions are welcome. Zonny is structured to make extension straightforward.

### Adding a New Tool

1. Create `tools/your_tool.py` with a function
2. Register it in `zonny/tool_registry.py`
3. Import it in `tools/__init__.py`

### Adding a New Agent

1. Create `agents/manifests/your_agent.yaml` with the agent's configuration
2. Create `agents/your_agent.py` with the agent logic
3. Register it in `agents/registry.py`

### Adding a New API Endpoint

1. Add the route to `server.py`
2. Add a corresponding MCP tool in `mcp_server.py` if applicable

### Code Standards

- Follow existing patterns in each module
- Keep each file focused on a single responsibility
- Add docstrings to public functions
- Run `python zonny_status.py` before submitting and verify all 35 checks pass

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.12 | Core runtime |
| Web Framework | FastAPI | HTTP server and REST API |
| ASGI Server | Uvicorn | Serves the FastAPI application |
| LLM Runtime | Ollama | Runs language models locally |
| Multi-Agent Framework | AutoGen (Microsoft) | Agent teams and orchestration |
| Vector Database | ChromaDB | Persistent semantic memory |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Text-to-vector conversion |
| Code Editor | Monaco Editor (CDN) | VS Code engine for the browser |
| Terminal Emulator | xterm.js (CDN) | Browser-based terminal |
| PDF Parsing | pypdf | Document ingestion |
| MCP Protocol | mcp Python SDK | Claude Desktop integration |

### Models Used

| Model | Size | Used For |
|-------|------|----------|
| nemotron-3-nano:latest | ~2 GB | Chat agents, CEO, Architect, QA, Reviewer |
| deepseek-coder:33b | ~19 GB | Frontend and Backend code generation |

---

## License

This project is open source. See the LICENSE file for details.
