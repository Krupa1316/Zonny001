"""
Memory System - Slice C Evolution

Slice C introduces:
• Session-based memory isolation
• Agent-scoped memory namespaces
• Document context separation

Memory Schema:
{
    "session": session_id,
    "agent": agent_name,
    "role": "user|assistant|document",
    "timestamp": unix_time
}

Key Principle:
Every agent has: (memory namespace) = session_id + agent_name

This ensures:
✅ Code agent can't see docs agent memories
✅ Router sees nothing (stateless)
✅ Sessions don't cross
✅ Agents remain focused
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pathlib import Path
import uuid
import time

DB_DIR = Path("chroma_memory")

embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

client = chromadb.Client(
    Settings(
        persist_directory=str(DB_DIR),
        anonymized_telemetry=False
    )
)

collection = client.get_or_create_collection("chat_memory")


# ============================================================
# Slice C - Session + Agent Scoped Memory
# ============================================================

def store(text, session, agent, role):
    """
    Store memory with session + agent isolation.
    
    Args:
        text: Content to store
        session: Session ID
        agent: Agent name (general, docs, code, memory)
        role: "user", "assistant", or "document"
    """
    embedding = embedder.encode(text).tolist()
    
    collection.add(
        documents=[text],
        embeddings=[embedding],
        ids=[str(uuid.uuid4())],
        metadatas=[{
            "session": session,
            "agent": agent,
            "role": role,
            "timestamp": time.time()
        }]
    )


def retrieve(query, session, agent, k=4):
    """
    Retrieve memory for specific session + agent.
    
    This enforces memory isolation:
    - Code agent never sees docs agent memories
    - Each session is isolated
    - Agent memories don't leak
    
    Args:
        query: Search query
        session: Session ID
        agent: Agent name
        k: Number of results
        
    Returns:
        List of retrieved text chunks
    """
    embedding = embedder.encode(query).tolist()
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=k,
        where={
            "$and": [
                {"session": {"$eq": session}},
                {"agent": {"$eq": agent}}
            ]
        }
    )
    
    if not results["documents"]:
        return []
    
    return results["documents"][0]


def retrieve_cross_agent(query, session, k=4):
    """
    Retrieve memory across all agents for a session.
    
    Used by memory agent to recall across contexts.
    
    Args:
        query: Search query
        session: Session ID
        k: Number of results
        
    Returns:
        List of (text, agent_name) tuples
    """
    embedding = embedder.encode(query).tolist()
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=k,
        where={"session": {"$eq": session}}
    )
    
    if not results["documents"] or not results["metadatas"]:
        return []
    
    # Return with agent attribution
    memories = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        memories.append((doc, meta.get("agent", "unknown")))
    
    return memories


# ============================================================
# Legacy Functions (Pre-Slice C) - Keep for backward compatibility
# ============================================================

# ---------------- Chunking ----------------

def chunk_text(text, size=500, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

# ---------------- Document Storage ----------------

def store_text_blocks(text, source="document", role="document", document_id="default", conversation_id="default"):
    chunks = chunk_text(text)

    for chunk in chunks:
        embedding = embedder.encode(chunk).tolist()

        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            ids=[str(uuid.uuid4())],
            metadatas=[{
                "role": role,
                "source": source,
                "document_id": document_id,
                "conversation_id": conversation_id,
                "timestamp": time.time()
            }]
        )


# ---------------- Chat Memory ----------------

def store_message(text, role="user", conversation_id="default"):
    embedding = embedder.encode(text).tolist()

    collection.add(
        documents=[text],
        embeddings=[embedding],
        ids=[str(uuid.uuid4())],
        metadatas=[{
            "role": role,
            "conversation_id": conversation_id,
            "timestamp": time.time()
        }]
    )

def retrieve_memory(query, conversation_id="default", document_id=None, top_k=4):
    embedding = embedder.encode(query).tolist()

    if document_id:
        where = {
            "$and": [
                {"conversation_id": conversation_id},
                {"document_id": document_id}
            ]
        }
    else:
        where = {"conversation_id": conversation_id}

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where
    )

    if not results["documents"]:
        return []

    return results["documents"][0]
