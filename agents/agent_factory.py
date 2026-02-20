"""
Agent Factory - Creates runtime agents from YAML manifests

Converts declarative YAML configs into executable agent instances.
"""

import requests
from typing import Dict, Any, Optional
from runtime.base import BaseAgent
from agents.manifest_loader import AgentManifest, ManifestLoader


class ManifestAgent(BaseAgent):
    """
    Dynamic agent created from a YAML manifest.
    
    This agent wraps the manifest configuration and executes tasks
    according to the declarative specification.
    """
    
    def __init__(self, manifest: AgentManifest, ollama_url: str = "http://localhost:11434/api/generate"):
        """
        Initialize agent from manifest.
        
        Args:
            manifest: The AgentManifest configuration
            ollama_url: Ollama API endpoint
        """
        self.manifest = manifest
        self.ollama_url = ollama_url
        self.name = manifest.name
        
        # Track iterations
        self._iteration_count = 0
    
    def execute(self, context, task: str) -> str:
        """
        Execute task according to manifest configuration.
        
        Args:
            context: AgentContext (execution state)
            task: Task description
            
        Returns:
            Agent's response string
        """
        # Check iteration limit
        if self._iteration_count >= self.manifest.max_iterations:
            return f"[{self.name}] Max iterations ({self.manifest.max_iterations}) reached"
        
        self._iteration_count += 1
        
        # Build prompt with system prompt + task
        prompt = f"""{self.manifest.system_prompt}

Task: {task}

Available tools: {', '.join(self.manifest.tools)}

Respond based on your role and available tools."""
        
        # Call LLM
        try:
            payload = {
                "model": "nemotron-3-nano:latest",
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
            
        except Exception as e:
            return f"[{self.name}] Error: {e}"
    
    def reset_iterations(self):
        """Reset iteration counter"""
        self._iteration_count = 0
    
    def __repr__(self):
        return f"ManifestAgent(name='{self.name}', priority={self.manifest.priority})"


class AgentFactory:
    """
    Factory for creating agents from manifests.
    
    Handles loading YAML files and instantiating agent instances.
    """
    
    def __init__(self, manifests_dir: str = "agents/manifests"):
        """
        Initialize factory.
        
        Args:
            manifests_dir: Path to manifest directory
        """
        self.loader = ManifestLoader(manifests_dir)
        self._agent_cache: Dict[str, ManifestAgent] = {}
    
    def create_agent(self, agent_name: str) -> Optional[ManifestAgent]:
        """
        Create an agent instance from its manifest.
        
        Args:
            agent_name: Name of agent (matches manifest name field)
            
        Returns:
            ManifestAgent instance or None if not found
        """
        # Check cache first
        if agent_name in self._agent_cache:
            return self._agent_cache[agent_name]
        
        # Load manifest
        manifests = self.loader.load_all_manifests()
        if agent_name not in manifests:
            return None
        
        manifest = manifests[agent_name]
        
        # Check if enabled
        if not manifest.enabled:
            print(f"⚠️  Agent '{agent_name}' is disabled in manifest")
            return None
        
        # Create agent
        agent = ManifestAgent(manifest)
        
        # Cache it
        self._agent_cache[agent_name] = agent
        
        return agent
    
    def create_all_agents(self) -> Dict[str, ManifestAgent]:
        """
        Create all enabled agents from manifests.
        
        Returns:
            Dictionary mapping agent name to ManifestAgent instance
        """
        agents = {}
        manifests = self.loader.get_enabled_agents()
        
        for name, manifest in manifests.items():
            agent = ManifestAgent(manifest)
            agents[name] = agent
            self._agent_cache[name] = agent
        
        return agents
    
    def list_available_agents(self) -> list:
        """List all available agent names"""
        manifests = self.loader.load_all_manifests()
        return list(manifests.keys())
    
    def list_enabled_agents(self) -> list:
        """List enabled agent names"""
        manifests = self.loader.get_enabled_agents()
        return list(manifests.keys())
    
    def get_manifest(self, agent_name: str) -> Optional[AgentManifest]:
        """Get the manifest for a specific agent"""
        manifests = self.loader.load_all_manifests()
        return manifests.get(agent_name)
    
    def clear_cache(self):
        """Clear the agent cache"""
        self._agent_cache.clear()
