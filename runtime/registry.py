"""
 Agent + Tool Registry

Dynamic registration system.

No imports of agents here.
No coupling to specific implementations.

This is how Claude Skills / Gemini Extensions work.
"""

import yaml
from pathlib import Path


class AgentRegistry:
    """
    Central registry for all agents and tools.
    
    Allows dynamic registration without hardcoding:
    - registry.register_agent(DocumentAgent())
    - registry.register_tool(ReadFileTool())
    
    Engine queries registry, never imports agents directly.
    """
    
    def __init__(self):
        self.agents = {}
        self.tools = {}
        self.manifests = {}  # Store agent manifests for SubAgentRunner
        self.enabled_agents = set()  # Track which agents are enabled (Phase 4)
    
    def register_agent(self, agent):
        """
        Register an agent.
        
        Args:
            agent: Instance of BaseAgent subclass
        """
        if not hasattr(agent, 'name'):
            raise ValueError("Agent must have 'name' attribute")
        
        self.agents[agent.name] = agent
        return agent
    
    def register_tool(self, tool):
        """
        Register a tool.
        
        Args:
            tool: Instance of BaseTool subclass
        """
        if not hasattr(tool, 'name'):
            raise ValueError("Tool must have 'name' attribute")
        
        self.tools[tool.name] = tool
        return tool
    
    def get_agent(self, name):
        """
        Retrieve agent by name.
        
        Returns:
            Agent instance or None
        """
        return self.agents.get(name)
    
    def get_tool(self, name):
        """
        Retrieve tool by name.
        
        Returns:
            Tool instance or None
        """
        return self.tools.get(name)
    
    def list_agents(self):
        """
        Get all agents with their enabled status (Phase 4).
        
        Returns:
            List of dicts with name, enabled, description
        """
        result = []
        for name, manifest in self.manifests.items():
            result.append({
                "name": name,
                "enabled": name in self.enabled_agents,
                "description": manifest.get("description", ""),
                "priority": manifest.get("priority", "medium"),
                "tools": manifest.get("tools", [])
            })
        return result
    
    def list_tools(self):
        """Get all registered tool names"""
        return list(self.tools.keys())
    
    def unregister_agent(self, name):
        """Remove agent from registry"""
        if name in self.agents:
            del self.agents[name]
    
    def unregister_tool(self, name):
        """Remove tool from registry"""
        if name in self.tools:
            del self.tools[name]
    
    def register_manifest(self, manifest):
        """
        Register an agent manifest (for SubAgentRunner).
        
        Args:
            manifest: AgentManifest instance or dict
        """
        if hasattr(manifest, 'name'):
            name = manifest.name
            # Convert to dict for SubAgentRunner
            manifest_dict = {
                'name': manifest.name,
                'description': manifest.description,
                'system_prompt': manifest.system_prompt,
                'tools': manifest.tools,
                'context_scope': manifest.context_scope,
                'max_iterations': manifest.max_iterations,
                'priority': manifest.priority,
                'enabled': manifest.enabled
            }
            self.manifests[name] = manifest_dict
            # Auto-enable if manifest says enabled=true (Phase 4)
            if manifest.enabled:
                self.enabled_agents.add(name)
        elif isinstance(manifest, dict) and 'name' in manifest:
            self.manifests[manifest['name']] = manifest
            # Auto-enable if manifest says enabled=true (Phase 4)
            if manifest.get('enabled', True):
                self.enabled_agents.add(manifest['name'])
        else:
            raise ValueError("Manifest must have 'name' field")
        
        return manifest
    
    def get_manifest(self, name):
        """Get manifest by name"""
        return self.manifests.get(name)
    
    def list_manifests(self):
        """Get all registered manifest names"""
        return list(self.manifests.keys())
    
    # Phase 4: Agent Management Methods
    
    def enable_agent(self, name):
        """
        Enable an agent.
        
        Args:
            name: Agent name
        """
        if name in self.manifests:
            self.enabled_agents.add(name)
            return True
        return False
    
    def disable_agent(self, name):
        """
        Disable an agent.
        
        Args:
            name: Agent name
        """
        self.enabled_agents.discard(name)
        return True
    
    def is_agent_enabled(self, name):
        """Check if agent is enabled"""
        return name in self.enabled_agents
    
    def load_manifests(self, path="agents/manifests"):
        """
        Load all manifests from directory (hot reload).
        
        Args:
            path: Path to manifests directory
        """
        manifest_path = Path(path)
        if not manifest_path.exists():
            raise ValueError(f"Manifests directory not found: {path}")
        
        # Clear existing manifests
        self.manifests.clear()
        # Keep enabled_agents set to preserve user preferences
        
        # Load all YAML files
        for file_path in manifest_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(file_path.read_text(encoding='utf-8'))
                if 'name' in data:
                    self.manifests[data['name']] = data
                    # Only auto-enable if not already in enabled_agents AND manifest says enabled
                    if data['name'] not in self.enabled_agents and data.get('enabled', True):
                        self.enabled_agents.add(data['name'])
            except Exception as e:
                print(f"Warning: Failed to load {file_path.name}: {e}")
        
        return len(self.manifests)
    
    def clear(self):
        """Clear all registrations (useful for testing)"""
        self.agents.clear()
        self.tools.clear()
        self.manifests.clear()
        self.enabled_agents.clear()
