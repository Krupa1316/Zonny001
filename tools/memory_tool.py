"""
MemoryTool - Access conversation history from ChromaDB

Retrieves past messages and conversation context.
"""

from runtime.base import BaseTool
from zonny.memory import retrieve_memory, collection


class MemoryTool(BaseTool):
    """
    Memory retrieval tool for accessing conversation history.
    
    Searches past interactions to maintain context continuity.
    """
    
    name = "memory_search"
    
    def execute(self, input_text: str) -> str:
        """
        Search conversation memory.
        
        Args:
            input_text: Query string to search for in past conversations
            
        Returns:
            Relevant past messages
        """
        try:
            # Search memory with filter for chat messages (not documents)
            results = retrieve_memory(input_text, top_k=3)
            
            if not results:
                return "No relevant conversation history found."
            
            # Format results
            output = "=== Past Conversations ===\n\n"
            for i, message in enumerate(results, 1):
                output += f"[Message {i}]\n{message}\n\n"
            
            return output
            
        except Exception as e:
            return f"Memory search error: {e}"
    
    def get_recent_messages(self, count: int = 5) -> str:
        """
        Get the most recent messages.
        
        Args:
            count: Number of recent messages to retrieve
            
        Returns:
            Recent messages formatted as string
        """
        try:
            # This is a simplified version - in production you'd query by timestamp
            results = collection.get(limit=count)
            
            if not results or not results.get("documents"):
                return "No recent messages found."
            
            output = "=== Recent Messages ===\n\n"
            for i, doc in enumerate(results["documents"], 1):
                output += f"[{i}] {doc}\n\n"
            
            return output
            
        except Exception as e:
            return f"Recent messages error: {e}"
    
    def __repr__(self):
        return f"MemoryTool(name='{self.name}')"
