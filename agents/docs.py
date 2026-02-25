"""
Slice E - Docs Agent with Document Memory + LLM

Handles document queries with:
- Document-scoped memory
- Isolated from other agents
- Real LLM responses with document context
"""

from agents.base import Agent
from zonny.memory import store, retrieve
import requests
import json


class DocsAgent(Agent):
    """
    Docs Agent - Handles document and PDF queries.
    
    Slice C: Now with document memory isolation.
    """
    
    name = "docs"
    description = "Handles document and PDF queries"
    
    def run(self, input: str, context: dict) -> str:
        """
        Handle document queries with isolated memory.
        
        Args:
            input: User input
            context: Execution context (must include session)
            
        Returns:
            Response string
        """
        session = context.get('session', 'unknown')
        
        # Slice E: Retrieve document memories
        doc_memories = retrieve(input, session, self.name, k=5)
        
        # Store user query
        store(input, session, self.name, "user")
        
        # Slice E: Call Ollama with document context
        if not doc_memories:
            response = " No documents uploaded yet. Upload PDFs using /v1/upload endpoint to query them."
        else:
            # Build document context for LLM
            doc_context = "\n\nRelevant document content:\n"
            for mem in doc_memories:
                doc_context += f"- {mem}\n"
            
            system_prompt = f"""You are a document analysis assistant (Docs Agent).
You help users understand and query their uploaded documents.

Answer based ONLY on the document content provided below.
If the answer isn't in the documents, say so.{doc_context}"""
            
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
                    response = f"[FAIL] LLM error: {llm_response.status_code}"
            except Exception as e:
                response = f"[FAIL] Error: {e}"
        
        # Store assistant response
        store(response, session, self.name, "assistant")
        
        return response
