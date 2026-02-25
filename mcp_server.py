"""
[BOT] MCP Coding Agent Server

A lightweight coding assistant MCP server that works like VS Code Copilot.
Uses your local Ollama + ChromaDB for intelligent code assistance.

Usage:
    python mcp_server.py

Or configure in Claude Desktop:
    {
      "mcpServers": {
        "local-coding-agent": {
          "command": "python",
          "args": ["/path/to/zonny/mcp_server.py"]
        }
      }
    }
"""

import asyncio
import json
from pathlib import Path
from typing import Any
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
import os
import re

# Lazy imports - only load when needed to speed up server startup
_orchestrator = None
_memory = None

def get_orchestrator():
    """Lazy import orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        from orchestrator import orchestrate, call_ollama
        _orchestrator = {'orchestrate': orchestrate, 'call_ollama': call_ollama}
    return _orchestrator

def get_memory():
    """Lazy import memory"""
    global _memory
    if _memory is None:
        from zonny.memory import store_text_blocks, retrieve_memory, collection
        _memory = {'store_text_blocks': store_text_blocks, 'retrieve_memory': retrieve_memory, 'collection': collection}
    return _memory

# Initialize MCP Server
app = Server("local-coding-agent")

# Workspace root (current directory by default)
WORKSPACE_ROOT = Path(__file__).parent

# ============================================
# [TOOL]️ CODING AGENT TOOLS
# ============================================

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """List all available coding tools"""
    return [
        types.Tool(
            name="read_file",
            description="Read contents of a file in the workspace. Returns the file content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from workspace root"
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="list_directory",
            description="List files and folders in a directory. Returns directory contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to directory (default: workspace root)",
                        "default": "."
                    }
                }
            }
        ),
        types.Tool(
            name="search_code",
            description="Search for code patterns or text in workspace files. Returns matching lines with context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text or regex pattern to search for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to search in (e.g., '*.py', '*.js')",
                        "default": "*"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="analyze_code",
            description="Analyze code structure, complexity, or get explanations. Uses local LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code snippet to analyze"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to do: 'explain', 'review', 'suggest', 'debug'",
                        "enum": ["explain", "review", "suggest", "debug"],
                        "default": "explain"
                    }
                },
                "required": ["code"]
            }
        ),
        types.Tool(
            name="get_project_context",
            description="Get overview of project structure and key files. Useful for understanding codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "What to focus on: 'structure', 'dependencies', 'architecture'",
                        "default": "structure"
                    }
                }
            }
        ),
        types.Tool(
            name="code_completion",
            description="Get code completion suggestions for the given context. Like Copilot autocomplete.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prefix": {
                        "type": "string",
                        "description": "Code before cursor"
                    },
                    "suffix": {
                        "type": "string",
                        "description": "Code after cursor (optional)",
                        "default": ""
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                        "default": "python"
                    }
                },
                "required": ["prefix"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "read_file":
            return await tool_read_file(arguments["path"])
        
        elif name == "list_directory":
            path = arguments.get("path", ".")
            return await tool_list_directory(path)
        
        elif name == "search_code":
            query = arguments["query"]
            pattern = arguments.get("file_pattern", "*")
            return await tool_search_code(query, pattern)
        
        elif name == "analyze_code":
            code = arguments["code"]
            task = arguments.get("task", "explain")
            return await tool_analyze_code(code, task)
        
        elif name == "get_project_context":
            focus = arguments.get("focus", "structure")
            return await tool_get_project_context(focus)
        
        elif name == "code_completion":
            prefix = arguments["prefix"]
            suffix = arguments.get("suffix", "")
            language = arguments.get("language", "python")
            return await tool_code_completion(prefix, suffix, language)
        
        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


# ============================================
# [DIR] TOOL IMPLEMENTATIONS
# ============================================

async def tool_read_file(path: str) -> list[types.TextContent]:
    """Read file contents"""
    file_path = WORKSPACE_ROOT / path
    
    if not file_path.exists():
        return [types.TextContent(
            type="text",
            text=f"[FAIL] File not found: {path}"
        )]
    
    if file_path.is_dir():
        return [types.TextContent(
            type="text",
            text=f"[FAIL] Path is a directory: {path}"
        )]
    
    try:
        content = file_path.read_text(encoding='utf-8')
        return [types.TextContent(
            type="text",
            text=f"[DOC] {path}\n\n```\n{content}\n```"
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"[FAIL] Error reading file: {e}"
        )]


async def tool_list_directory(path: str) -> list[types.TextContent]:
    """List directory contents"""
    dir_path = WORKSPACE_ROOT / path
    
    if not dir_path.exists():
        return [types.TextContent(
            type="text",
            text=f"[FAIL] Directory not found: {path}"
        )]
    
    if not dir_path.is_dir():
        return [types.TextContent(
            type="text",
            text=f"[FAIL] Path is not a directory: {path}"
        )]
    
    items = []
    for item in sorted(dir_path.iterdir()):
        if item.name.startswith('.'):
            continue
        icon = "[DIR]" if item.is_dir() else "[DOC]"
        items.append(f"{icon} {item.name}")
    
    return [types.TextContent(
        type="text",
        text=f"[DIR] {path}\n\n" + "\n".join(items)
    )]


async def tool_search_code(query: str, file_pattern: str) -> list[types.TextContent]:
    """Search code in workspace"""
    results = []
    pattern = re.compile(query, re.IGNORECASE)
    
    # Search through files
    for file_path in WORKSPACE_ROOT.rglob(file_pattern):
        if file_path.is_file() and not any(p.startswith('.') for p in file_path.parts):
            try:
                content = file_path.read_text(encoding='utf-8')
                matches = []
                
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        matches.append(f" Line {i}: {line.strip()}")
                
                if matches:
                    rel_path = file_path.relative_to(WORKSPACE_ROOT)
                    results.append(f"[DOC] {rel_path}\n" + "\n".join(matches))
            except:
                pass
    
    if not results:
        return [types.TextContent(
            type="text",
            text=f"No matches found for: {query}"
        )]
    
    return [types.TextContent(
        type="text",
        text="\n\n".join(results)
    )]


async def tool_analyze_code(code: str, task: str) -> list[types.TextContent]:
    """Analyze code using local LLM"""
    
    prompts = {
        "explain": "Explain what this code does in clear terms:",
        "review": "Review this code for potential issues, bugs, or improvements:",
        "suggest": "Suggest improvements or optimizations for this code:",
        "debug": "Help debug this code. Identify potential issues:"
    }
    
    prompt = f"""{prompts.get(task, prompts['explain'])}

```
{code}
```

Provide a clear, concise response:"""
    
    # Use local Ollama (wrap in to_thread for async compatibility)
    orchestrator = get_orchestrator()
    response = await asyncio.to_thread(
        orchestrator['call_ollama'],
        prompt,
        system="You are an expert code analyst. Be concise and practical."
    )
    
    return [types.TextContent(
        type="text",
        text=response
    )]


async def tool_get_project_context(focus: str) -> list[types.TextContent]:
    """Get project structure overview"""
    
    structure = []
    file_types = {}
    
    # Analyze project
    for file_path in WORKSPACE_ROOT.rglob("*"):
        if file_path.is_file() and not any(p.startswith('.') for p in file_path.parts):
            ext = file_path.suffix or 'no-ext'
            file_types[ext] = file_types.get(ext, 0) + 1
            
            # Key files
            if file_path.name in ['server.py', 'orchestrator.py', 'memory.py', 'README.md', 'requirements.txt']:
                rel_path = file_path.relative_to(WORKSPACE_ROOT)
                structure.append(f"[DOC] {rel_path}")
    
    file_summary = "\n".join([f" {ext}: {count} files" for ext, count in sorted(file_types.items())])
    key_files = "\n".join(structure) if structure else " (analyzing...)"
    
    context = f"""[ARCH]️ Project Context

[DIR] File Types:
{file_summary}

 Key Files:
{key_files}

[IDEA] Focus: {focus}
"""
    
    return [types.TextContent(
        type="text",
        text=context
    )]


async def tool_code_completion(prefix: str, suffix: str, language: str) -> list[types.TextContent]:
    """Generate code completion"""
    
    prompt = f"""Complete the following {language} code. Provide ONLY the completion, no explanations.

Code before cursor:
```{language}
{prefix}
```

Code after cursor:
```{language}
{suffix}
```

Completion:"""
    
    # Use local Ollama (wrap in to_thread for async compatibility)
    orchestrator = get_orchestrator()
    completion = await asyncio.to_thread(
        orchestrator['call_ollama'],
        prompt,
        system="You are a code completion assistant. Output only code, no explanations."
    )
    
    # Clean up completion
    completion = completion.strip()
    if completion.startswith("```"):
        lines = completion.split("\n")
        completion = "\n".join(lines[1:-1]) if len(lines) > 2 else ""
    
    return [types.TextContent(
        type="text",
        text=completion
    )]


# ============================================
# RESOURCES (Optional)
# ============================================

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    """Expose project files as resources"""
    resources = []
    
    for file_path in WORKSPACE_ROOT.rglob("*.py"):
        if not any(p.startswith('.') for p in file_path.parts):
            rel_path = file_path.relative_to(WORKSPACE_ROOT)
            resources.append(types.Resource(
                uri=f"file:///{rel_path}",
                name=str(rel_path),
                mimeType="text/x-python",
                description=f"Python file: {rel_path}"
            ))
    
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource content"""
    # Remove file:/// prefix
    path = uri.replace("file:///", "")
    file_path = WORKSPACE_ROOT / path
    
    if file_path.exists():
        return file_path.read_text(encoding='utf-8')
    
    return f"Resource not found: {uri}"


# ============================================
# [START] MAIN
# ============================================

async def main():
    """Run MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    print("[BOT] Starting Local Coding Agent MCP Server...", flush=True)
    asyncio.run(main())
