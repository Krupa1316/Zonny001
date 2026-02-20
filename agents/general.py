"""
Slice E - General Agent with Memory + LLM

Handles general conversation with:
- Session-scoped memory
- Agent-isolated context
- Real LLM responses using Ollama
"""

from agents.base import Agent
from zonny.memory import store, retrieve
import requests
import json


class GeneralAgent(Agent):
    """
    General Agent - Fallback for all queries.
    
    Slice C: Now with isolated memory.
    """
    
    name = "general"
    description = "General purpose agent for conversation and questions"
    
    def run(self, input: str, context: dict) -> str:
        """
        Handle general queries with memory.
        
        Args:
            input: User input
            context: Execution context (must include session)
            
        Returns:
            Response string
        """
        session = context.get('session', 'unknown')
        
        if not input:
            return "👋 Hello! I'm the general agent. How can I help?"
        
        # Slice E: Retrieve relevant memories
        memories = retrieve(input, session, self.name, k=3)
        
        # Build memory context for LLM
        memory_context = ""
        if memories:
            memory_context = "\n\nRelevant conversation history:\n"
            for mem in memories:
                memory_context += f"- {mem}\n"
        
        # Store user input
        store(input, session, self.name, "user")
        
        # Slice E: Call Ollama for real LLM response
        system_prompt = f"""You are a helpful AI assistant (General Agent).
You handle general conversation, questions, and help users with various tasks.

Be friendly, concise, and helpful.{memory_context}"""
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "nemotron-3-nano:latest",
                    "prompt": input,
                    "system": system_prompt,
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result.get("response", "No response from LLM")
            else:
                llm_response = f"❌ LLM error: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            llm_response = "❌ Cannot connect to Ollama. Is it running?\n\nRun: ollama serve"
        except Exception as e:
            llm_response = f"❌ Error calling LLM: {e}"
        
        # Store assistant response
        store(llm_response, session, self.name, "assistant")
        
        return llm_response
