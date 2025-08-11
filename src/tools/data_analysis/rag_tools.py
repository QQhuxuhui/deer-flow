"""
RAG (Retrieval-Augmented Generation) Tools for DeerFlow Data Analysis

Provides domain-specific knowledge retrieval using FAISS vector store.
Adapted from external data analysis module with DeerFlow integration.
"""

import os
from typing import Optional
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.tools.retriever import create_retriever_tool
from pydantic import BaseModel, Field

from src.config.configuration import Configuration


class DomainQuerySchema(BaseModel):
    """Schema for domain knowledge query tool."""
    query: str = Field(
        description="Query string to search in the domain knowledge base"
    )
    k: int = Field(
        description="Number of relevant documents to retrieve",
        default=3
    )


def _get_embeddings_model(config: Configuration = None) -> OpenAIEmbeddings:
    """
    Initialize embeddings model using DeerFlow configuration.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        OpenAIEmbeddings: Configured embeddings model
    """
    # Get API configuration from environment or config
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://ai.devtool.tech/proxy/v1")
    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    return OpenAIEmbeddings(
        api_key=api_key,
        base_url=base_url,
        model=model_name
    )


def _get_vector_store_path(config: Configuration = None) -> str:
    """
    Get vector store path from configuration.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        Path to vector store directory
    """
    if config and hasattr(config, 'vector_store_path'):
        return config.vector_store_path
    
    # Default path - check if external data exists
    external_path = "/usr/src/workspace/github/QQhuxuhui/deer-flow/external/data_agent/telco_customer_churn_analytics_handbook"
    if os.path.exists(external_path):
        return external_path
    
    # Fallback to project-relative path
    return os.path.join(os.getcwd(), "knowledge_base", "telco_customer_churn_analytics_handbook")


def _initialize_vector_store(config: Configuration = None) -> Optional[FAISS]:
    """
    Initialize FAISS vector store for domain knowledge retrieval.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        FAISS vector store or None if initialization fails
    """
    try:
        embeddings = _get_embeddings_model(config)
        vector_store_path = _get_vector_store_path(config)
        
        if not os.path.exists(vector_store_path):
            raise FileNotFoundError(f"Vector store not found at: {vector_store_path}")
        
        vector_store = FAISS.load_local(
            folder_path=vector_store_path,
            embeddings=embeddings,
            allow_dangerous_deserialization=True
        )
        
        return vector_store
        
    except Exception as e:
        print(f"Warning: Failed to initialize vector store: {e}")
        return None


# Global vector store instance (initialized lazily)
_vector_store = None


def _get_vector_store() -> Optional[FAISS]:
    """Get or initialize the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = _initialize_vector_store()
    return _vector_store


@tool(args_schema=DomainQuerySchema)
def domain_knowledge_tool(query: str, k: int = 3) -> str:
    """
    Search domain-specific knowledge base for relevant information.
    
    This tool searches the telecom customer churn analytics handbook 
    using vector similarity to find relevant sections for the given query.
    Use this when you need domain expertise or business context for
    data analysis tasks.
    
    Topics covered include:
    - Customer churn prediction strategies
    - Data dictionary and feature definitions  
    - Modeling approaches and best practices
    - Business insights and interpretations
    - Feature engineering techniques
    
    Args:
        query: Search query for domain knowledge
        k: Number of relevant documents to retrieve (default: 3)
        
    Returns:
        Retrieved relevant information or error message
    """
    try:
        vector_store = _get_vector_store()
        if not vector_store:
            return "❌ Domain knowledge base is not available. Please ensure vector store is properly configured."
        
        # Perform similarity search
        docs = vector_store.similarity_search(query, k=k)
        
        if not docs:
            return "ℹ️ No relevant information found in the domain knowledge base for this query."
        
        # Format results
        results = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content.strip()
            metadata = doc.metadata
            
            result = f"**Document {i}:**\n{content}"
            if metadata:
                result += f"\n*Metadata: {metadata}*"
            results.append(result)
        
        return "\n\n" + "\n\n".join(results)
        
    except Exception as e:
        return f"❌ Domain knowledge search failed: {str(e)}"


# Create retriever tool for compatibility with LangChain agents
def create_domain_retriever_tool(config: Configuration = None):
    """
    Create a LangChain retriever tool for domain knowledge.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        LangChain retriever tool or None if vector store unavailable
    """
    vector_store = _get_vector_store()
    if not vector_store:
        return None
        
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    return create_retriever_tool(
        retriever,
        name="retrieve_telco_handbook",
        description="Search and return relevant sections from the Telecom Customer Churn Analytics Handbook for domain-specific questions about customer churn prediction, data analysis, and business insights."
    )


# Tool list for easy import
rag_tools = [domain_knowledge_tool]