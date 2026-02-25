"""
[BRAIN] Orchestrator Agent Architecture

Flow:
1. Decider analyzes user intent → returns JSON
2. Python executes specialist functions
3. Decider synthesizes final response

Agents communicate ONLY through the Decider.
"""

import requests
import json
from zonny.memory import retrieve_memory, store_text_blocks, collection

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "nemotron-3-nano:latest"

# ============================================
# [TOOL] SPECIALIST AGENT FUNCTIONS
# ============================================

def document_agent(query: str, document_id: str, conversation_id: str, top_k: int = 5) -> str:
    """
    [DOC] Document Agent
    Retrieves relevant chunks from uploaded documents.
    """
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    
    embedding = embedder.encode(query).tolist()
    
    where = {
        "$and": [
            {"conversation_id": conversation_id},
            {"document_id": document_id},
            {"role": "document"}
        ]
    }
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where
    )
    
    if not results["documents"] or not results["documents"][0]:
        return "No document context found."
    
    chunks = results["documents"][0]
    return "\n\n".join([f"[Doc Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)])


def memory_agent(query: str, conversation_id: str, top_k: int = 4) -> str:
    """
    [MODULE] Memory Agent
    Retrieves relevant conversation history.
    """
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    
    embedding = embedder.encode(query).tolist()
    
    where = {
        "$and": [
            {"conversation_id": conversation_id},
            {"role": {"$in": ["user", "assistant"]}}
        ]
    }
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where
    )
    
    if not results["documents"] or not results["documents"][0]:
        return "No conversation history found."
    
    memories = results["documents"][0]
    metadatas = results["metadatas"][0]
    
    formatted = []
    for mem, meta in zip(memories, metadatas):
        role = meta.get("role", "unknown").upper()
        formatted.append(f"[{role}]: {mem}")
    
    return "\n".join(formatted)


def code_agent(query: str) -> str:
    """
    [CODE] Code Agent
    Provides code-specific context and help.
    Currently returns guidance message - can be expanded.
    """
    return """Code Agent Context:
- This is a FastAPI + Ollama + ChromaDB RAG system
- Main components: server.py, memory.py, orchestrator.py
- Stack: Python, FastAPI, sentence-transformers, chromadb
- Model: nemotron-3-nano:latest via Ollama
"""


# ============================================
# [BRAIN] ORCHESTRATOR DECIDER
# ============================================

def call_ollama(prompt: str, system: str = None) -> str:
    """Helper to call Ollama API"""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False
    }, timeout=120) # Slice E: Match other timeouts (120s for local model)
    
    result = json.loads(response.text.strip().splitlines()[-1])
    return result["response"]


def decide_agents(user_message: str) -> dict:
    """
    [BRAIN] Step 1: Decider analyzes user intent
    Returns which agents to invoke
    """
    
    system_prompt = """You are an AI orchestrator. Your job is to analyze user requests and decide which specialist agents to invoke.

Available agents:
- "document" – when user asks about uploaded files, PDFs, documents
- "memory" – when user references previous conversation or needs context recall
- "code" – when user asks about programming, debugging, system architecture

Rules:
- Output ONLY valid JSON
- No explanation, no markdown, just JSON
- Format: {"agents": ["agent1", "agent2"], "reasoning": "brief reason"}
- You can select 0, 1, or multiple agents
- If user is just chatting, return empty agents array

Example responses:
{"agents": ["document"], "reasoning": "user asking about uploaded PDF"}
{"agents": ["memory", "document"], "reasoning": "needs previous context and doc info"}
{"agents": [], "reasoning": "simple greeting"}
"""

    prompt = f"""User message: {user_message}

Respond with JSON only:"""

    response = call_ollama(prompt, system_prompt)
    
    # Extract JSON from response (handle if LLM adds extra text)
    try:
        # Try to find JSON in response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            decision = json.loads(json_str)
            return decision
        else:
            # Fallback: no agents
            return {"agents": [], "reasoning": "parse_error"}
    except:
        # Fallback: use all agents if parsing fails
        return {"agents": ["memory"], "reasoning": "fallback"}


def execute_agents(decision: dict, user_message: str, conversation_id: str, document_id: str = None) -> dict:
    """
    [TOOL] Step 2: Execute specialist agent functions
    Returns gathered context from each agent
    """
    
    context = {}
    agents = decision.get("agents", [])
    
    if "document" in agents and document_id:
        context["document"] = document_agent(user_message, document_id, conversation_id)
    
    if "memory" in agents:
        context["memory"] = memory_agent(user_message, conversation_id)
    
    if "code" in agents:
        context["code"] = code_agent(user_message)
    
    return context


def synthesize_response(user_message: str, context: dict, decision: dict) -> str:
    """
    [BRAIN] Step 3: Final LLM call to synthesize response
    Uses gathered context to produce final answer
    """
    
    # Build context block
    context_parts = []
    
    if context.get("document"):
        context_parts.append(f"=== DOCUMENT CONTEXT ===\n{context['document']}")
    
    if context.get("memory"):
        context_parts.append(f"=== CONVERSATION MEMORY ===\n{context['memory']}")
    
    if context.get("code"):
        context_parts.append(f"=== CODE CONTEXT ===\n{context['code']}")
    
    context_block = "\n\n".join(context_parts) if context_parts else "No additional context."
    
    system_prompt = """You are a helpful AI assistant. Use the provided context to answer the user's question accurately. If context is provided, reference it in your answer. Be concise and helpful."""
    
    prompt = f"""{context_block}

=== USER MESSAGE ===
{user_message}

Provide a helpful response:"""
    
    return call_ollama(prompt, system_prompt)


# ============================================
# [TARGET] MAIN ORCHESTRATOR
# ============================================

def orchestrate(user_message: str, conversation_id: str, document_id: str = None) -> tuple[str, dict]:
    """
    Main orchestrator function
    
    Returns: (response, debug_info)
    """
    
    # Step 1: Decide which agents to use
    decision = decide_agents(user_message)
    
    # Step 2: Execute agent functions
    context = execute_agents(decision, user_message, conversation_id, document_id)
    
    # Step 3: Synthesize final response
    response = synthesize_response(user_message, context, decision)
    
    # Debug info for transparency
    debug_info = {
        "decision": decision,
        "agents_used": list(context.keys()),
        "context_sizes": {k: len(v) for k, v in context.items()}
    }
    
    return response, debug_info
