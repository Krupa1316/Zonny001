"""
Agent Manifest Loader

Loads and validates agent definitions from YAML files.
Declarative agent configuration inspired by Gemini CLI but using pure YAML.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class AgentManifest:
    """Parsed agent manifest with all configuration"""
    name: str
    description: str
    system_prompt: str
    tools: List[str]
    context_scope: str  # "shared" or "isolated"
    max_iterations: int
    priority: str  # "low", "medium", "high", "critical"
    enabled: bool
    metadata: Dict[str, Any]
    
    # Original YAML path for reference
    manifest_path: Optional[Path] = None
    
    def __repr__(self):
        return f"AgentManifest(name='{self.name}', tools={len(self.tools)}, enabled={self.enabled})"


class ManifestLoader:
    """Load and validate agent manifests from YAML files"""
    
    REQUIRED_FIELDS = [
        'name', 'description', 'system_prompt', 'tools',
        'context_scope', 'max_iterations', 'priority', 'enabled'
    ]
    
    VALID_CONTEXT_SCOPES = ['shared', 'isolated']
    VALID_PRIORITIES = ['low', 'medium', 'high', 'critical']
    
    def __init__(self, manifests_dir: str = "agents/manifests"):
        """
        Initialize manifest loader.
        
        Args:
            manifests_dir: Path to directory containing YAML manifests
        """
        self.manifests_dir = Path(manifests_dir)
        if not self.manifests_dir.exists():
            raise ValueError(f"Manifests directory not found: {manifests_dir}")
    
    def load_manifest(self, yaml_path: Path) -> AgentManifest:
        """
        Load a single YAML manifest file.
        
        Args:
            yaml_path: Path to YAML file
            
        Returns:
            Parsed AgentManifest
            
        Raises:
            ValueError: If manifest is invalid
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Validate required fields
        missing = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Manifest {yaml_path.name} missing fields: {missing}")
        
        # Validate context_scope
        if data['context_scope'] not in self.VALID_CONTEXT_SCOPES:
            raise ValueError(
                f"Invalid context_scope '{data['context_scope']}' in {yaml_path.name}. "
                f"Must be one of: {self.VALID_CONTEXT_SCOPES}"
            )
        
        # Validate priority
        if data['priority'] not in self.VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority '{data['priority']}' in {yaml_path.name}. "
                f"Must be one of: {self.VALID_PRIORITIES}"
            )
        
        # Validate max_iterations
        if not isinstance(data['max_iterations'], int) or data['max_iterations'] < 1:
            raise ValueError(f"max_iterations must be positive integer in {yaml_path.name}")
        
        # Validate tools is a list
        if not isinstance(data['tools'], list):
            raise ValueError(f"tools must be a list in {yaml_path.name}")
        
        # Create manifest object
        manifest = AgentManifest(
            name=data['name'],
            description=data['description'],
            system_prompt=data['system_prompt'],
            tools=data['tools'],
            context_scope=data['context_scope'],
            max_iterations=data['max_iterations'],
            priority=data['priority'],
            enabled=data['enabled'],
            metadata=data.get('metadata', {}),
            manifest_path=yaml_path
        )
        
        return manifest
    
    def load_all_manifests(self) -> Dict[str, AgentManifest]:
        """
        Load all YAML manifests from the manifests directory.
        
        Returns:
            Dictionary mapping agent name to AgentManifest
        """
        manifests = {}
        
        # Find all .yaml and .yml files
        yaml_files = list(self.manifests_dir.glob("*.yaml"))
        yaml_files.extend(self.manifests_dir.glob("*.yml"))
        
        for yaml_path in yaml_files:
            try:
                manifest = self.load_manifest(yaml_path)
                manifests[manifest.name] = manifest
            except Exception as e:
                print(f"⚠️  Warning: Failed to load {yaml_path.name}: {e}")
        
        return manifests
    
    def get_enabled_agents(self) -> Dict[str, AgentManifest]:
        """Get only enabled agents"""
        all_manifests = self.load_all_manifests()
        return {name: manifest for name, manifest in all_manifests.items() if manifest.enabled}
    
    def get_agents_by_priority(self, priority: str) -> Dict[str, AgentManifest]:
        """Get agents filtered by priority level"""
        all_manifests = self.load_all_manifests()
        return {name: manifest for name, manifest in all_manifests.items() 
                if manifest.priority == priority and manifest.enabled}
    
    def get_agents_with_tool(self, tool_name: str) -> Dict[str, AgentManifest]:
        """Get all agents that have a specific tool"""
        all_manifests = self.load_all_manifests()
        return {name: manifest for name, manifest in all_manifests.items() 
                if tool_name in manifest.tools and manifest.enabled}


def print_manifest_summary(manifest: AgentManifest):
    """Pretty print a manifest summary"""
    print(f"\n{'='*70}")
    print(f"📄 Agent: {manifest.name}")
    print(f"{'='*70}")
    print(f"Description: {manifest.description}")
    print(f"Context Scope: {manifest.context_scope}")
    print(f"Priority: {manifest.priority}")
    print(f"Max Iterations: {manifest.max_iterations}")
    print(f"Enabled: {'✅' if manifest.enabled else '❌'}")
    print(f"\n🔧 Tools ({len(manifest.tools)}):")
    for tool in manifest.tools:
        print(f"   - {tool}")
    print(f"\n💬 System Prompt:")
    # Show first 2 lines of prompt
    lines = manifest.system_prompt.strip().split('\n')
    for line in lines[:2]:
        print(f"   {line}")
    if len(lines) > 2:
        print(f"   ... ({len(lines)-2} more lines)")
    print()
