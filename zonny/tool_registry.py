"""
Zonny Tool Registry - The Source of Truth

This defines EVERYTHING Zonny can do.
Every capability is a tool.

Router Agent uses this to decide what to invoke.
Dispatcher uses this to execute.
"""

# Complete tool registry with rich descriptions for LLM reasoning
TOOLS = [
    # Filesystem Operations
    {
        "name": "filesystem.list",
        "description": "List files and directories in a path. Use this to discover what exists before reading. Shows file names, sizes, and types. Fast operation.",
        "args": ["path"],
        "category": "filesystem",
        "capability": "list",
        "use_when": "Need to see directory contents, check if files exist, or explore project structure"
    },
    {
        "name": "filesystem.read",
        "description": "Read complete contents of a file. Returns file text for analysis. Check if file exists first with filesystem.list to avoid errors.",
        "args": ["path"],
        "category": "filesystem",
        "capability": "read",
        "use_when": "Need to read code, config files, documentation, or existing analysis reports"
    },
    {
        "name": "filesystem.search",
        "description": "Search for files matching patterns (wildcards like *.py, *.json). Recursive search across directories. Returns list of matching paths.",
        "args": ["pattern", "directory"],
        "category": "filesystem",
        "capability": "search",
        "use_when": "Looking for specific file types, searching for files by name pattern"
    },
    {
        "name": "filesystem.write",
        "description": "Write or update file contents. Creates file if doesn't exist. Use for saving results, creating configs, or modifying code.",
        "args": ["path", "content"],
        "category": "filesystem",
        "capability": "write",
        "use_when": "Need to save data, create new files, or update existing content"
    },
    
    # Workspace Awareness
    {
        "name": "workspace.scan",
        "description": "Quick statistical overview of workspace: file counts, directory structure, languages detected. Lightweight operation for initial understanding.",
        "args": [],
        "category": "workspace",
        "capability": "scan",
        "use_when": "Need quick project stats or initial overview without deep analysis"
    },
    {
        "name": "workspace.tree",
        "description": "Visual hierarchical tree of all directories and files. Shows project structure at a glance. Good for understanding organization.",
        "args": [],
        "category": "workspace",
        "capability": "tree",
        "use_when": "User wants to see project layout, understand folder structure, navigate codebase"
    },
    {
        "name": "workspace.report",
        "description": "Deep comprehensive analysis: file statistics, code metrics, dependencies, structure analysis. Generates detailed report file (5-10KB). Expensive operation - only use when thorough analysis needed.",
        "args": ["output_file"],
        "category": "workspace",
        "capability": "report",
        "use_when": "User needs full project analysis, comprehensive understanding, or detailed documentation"
    },
    
    # Git Operations
    {
        "name": "git.status",
        "description": "Check git repository status: modified files, staged changes, branch info, commit status. Shows what changed in version control.",
        "args": [],
        "category": "git",
        "capability": "git_status",
        "use_when": "User asks about changes, git status, modified files, or version control state"
    },
    
    # Code Analysis
    {
        "name": "code.explain",
        "description": "Explain specific code concepts, functions, or programming patterns. For conceptual questions about code.",
        "args": ["query"],
        "category": "code",
        "capability": "explain",
        "use_when": "User asks how code works, what a function does, or needs programming concept explained"
    },
    {
        "name": "code.analyze",
        "description": "Deep analysis of code file: complexity, patterns, issues, suggestions. For code review and quality checks.",
        "args": ["file"],
        "category": "code",
        "capability": "analyze",
        "use_when": "User wants code review, quality analysis, or detailed file examination"
    },
    
    # Document Operations
    {
        "name": "docs.query",
        "description": "Search and query uploaded PDF documents. Semantic search across document content. Requires PDFs uploaded to system.",
        "args": ["query"],
        "category": "docs",
        "capability": "query_docs",
        "use_when": "User asks about document content, searches PDFs, or queries uploaded files"
    },
    
    # Memory Operations
    {
        "name": "memory.recall",
        "description": "Recall information from past conversations, previous context, or session history. Semantic memory search.",
        "args": ["query"],
        "category": "memory",
        "capability": "recall",
        "use_when": "User references past discussions, asks 'remember when', or needs previous context"
    },
    
    # System Commands
    {
        "name": "system.status",
        "description": "Get current system status: active agents, available tools, session info, runtime state.",
        "args": [],
        "category": "system",
        "capability": "status",
        "use_when": "User asks about system state, what's available, or Zonny capabilities"
    },
    {
        "name": "system.agents",
        "description": "List all available agent types and their capabilities. Shows what specialized agents can be invoked.",
        "args": [],
        "category": "system",
        "capability": "list_agents",
        "use_when": "User asks what agents exist or what Zonny can do"
    },
    {
        "name": "system.tools",
        "description": "List all available tools with descriptions. Complete capability inventory.",
        "args": [],
        "category": "system",
        "capability": "list_tools",
        "use_when": "User asks what tools exist, what operations available, or needs capability list"
    },
    {
        "name": "system.help",
        "description": "Show help information, usage guide, and available commands. User documentation.",
        "args": [],
        "category": "system",
        "capability": "help",
        "use_when": "User asks for help, usage instructions, or how to use Zonny"
    },
    
    # General Chat
    {
        "name": "chat.general",
        "description": "Natural conversation, answer questions, discuss topics. For general non-tool queries.",
        "args": ["message"],
        "capability": "chat",
        "category": "chat",
        "use_when": "Casual conversation, general questions, or when no specific tool applies"
    }
]


def get_tools_json():
    """Get tools as JSON for LLM context"""
    import json
    return json.dumps(TOOLS, indent=2)


def get_tool_by_name(name: str):
    """Get tool definition by name"""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def has_tool(name: str) -> bool:
    """Check if a tool exists in the registry"""
    return get_tool_by_name(name) is not None


def get_tools_by_category(category: str):
    """Get all tools in a category"""
    return [t for t in TOOLS if t["category"] == category]


def find_by_capability(capability: str):
    """Find first tool with the specified capability. Returns tool name or None."""
    for tool in TOOLS:
        if tool.get("capability") == capability:
            return tool["name"]
    return None


def get_tools_by_capability(capability: str):
    """Get all tools with the specified capability"""
    return [t for t in TOOLS if t.get("capability") == capability]


def list_tool_names():
    """Get list of all tool names"""
    return [t["name"] for t in TOOLS]
