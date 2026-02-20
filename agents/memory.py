"""
Slice E - Memory Agent with Cross-Agent Retrieval + LLM

Special agent that can:
- Retrieve across ALL agents in a session
- Provide unified memory view
- Real LLM responses with cross-agent context

This is the ONLY agent that breaks isolation (by design).
"""

from agents.base import Agent
from zonny.memory import store, retrieve_cross_agent
import requests
import json


class MemoryAgent(Agent):
    """
    Memory Agent - Handles recall and history queries.
    
    Slice C: Can retrieve memories across all agents in session.
    This is intentional - memory agent provides unified view.
    """
    
    name = "memory"
    description = "Handles memory recall and conversation history"
    
    def run(self, input: str, context: dict) -> str:
        """
        Handle memory queries with cross-agent retrieval.
        
        Args:
            input: User input
            context: Execution context (must include session)
            
        Returns:
            Response string
        """
        session = context.get('session', 'unknown')
        
        # Slice E: Retrieve across ALL agents
        cross_memories = retrieve_cross_agent(input, session, k=10)
        
        # Store user query
        store(input, session, self.name, "user")
        
        # Slice E: Call Ollama with cross-agent context
        if not cross_memories:
            response = "📭 No conversation history found in this session yet."
        else:
            # Build cross-agent context for LLM
            memory_context = "\n\nConversation history across agents:\n"
            for (mem, agent) in cross_memories:
                memory_context += f"[{agent}] {mem}\n"
            
            system_prompt = f"""You are a memory assistant (Memory Agent).
You help users recall and understand their conversation history.

You have access to the ENTIRE conversation history across all agents.
Summarize, recall, or answer questions about past interactions.{memory_context}"""
            
            try:
                llm_response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "nemotron-3-nano:latest",
                        "prompt": input,
                        "system": system_prompt,
                        "stream": False
                    },
                    timeout=120
                )
                
                if llm_response.status_code == 200:
                    result = llm_response.json()
                    response = result.get("response", "No response from LLM")
                else:
                    response = f"❌ LLM error: {llm_response.status_code}"
            except Exception as e:
                response = f"❌ Error: {e}"
        
        # Store assistant response
        store(response, session, self.name, "assistant")
        
        return response
