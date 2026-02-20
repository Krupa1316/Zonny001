"""
VectorTool - Retrieves relevant chunks from ChromaDB using vector search

Wraps the existing memory.py retrieval logic into a tool interface.
"""

from runtime.base import BaseTool
from zonny.memory import retrieve_memory


class VectorTool(BaseTool):
    """
    Vector search tool for RAG (Retrieval Augmented Generation).
    
    Searches the ChromaDB collection for relevant document chunks
    based on semantic similarity.
    """
    
    name = "vector_search"
    
    def execute(self, input_text: str) -> str:
        """
        Execute vector search.
        
        Args:
            input_text: Query string to search for
            
        Returns:
            Relevant chunks concatenated as string
        """
        try:
            # Retrieve relevant chunks
            results = retrieve_memory(input_text, top_k=3)
            
            if not results:
                return "No relevant documents found in vector database."
            
            # Format results
            output = "=== Retrieved Documents ===\n\n"
            for i, chunk in enumerate(results, 1):
                output += f"[Chunk {i}]\n{chunk}\n\n"
            
            return output
            
        except Exception as e:
            return f"Vector search error: {e}"
    
    def __repr__(self):
        return f"VectorTool(name='{self.name}')"
