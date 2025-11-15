"""Basic tests for Behind Bars bot."""

import pytest
from pathlib import Path

from behind_bars_bot.knowledge_base import KnowledgeBase
from behind_bars_bot.context7_tool import get_context7_search


@pytest.fixture
def knowledge_path():
    """Get path to knowledge directory."""
    return Path(__file__).parent.parent / "knowledge"


@pytest.mark.asyncio
async def test_knowledge_base_initialization(knowledge_path):
    """Test knowledge base initialization."""
    kb = KnowledgeBase(knowledge_path=knowledge_path, use_embeddings=False)
    await kb.initialize()
    
    assert kb._initialized
    assert len(kb.index) > 0


@pytest.mark.asyncio
async def test_knowledge_base_search(knowledge_path):
    """Test knowledge base search."""
    kb = KnowledgeBase(knowledge_path=knowledge_path, use_embeddings=False)
    await kb.initialize()
    
    results = await kb.search("jail", max_results=3)
    assert len(results) > 0
    assert all("path" in r for r in results)
    assert all("snippet" in r for r in results)


@pytest.mark.asyncio
async def test_knowledge_base_rag_search(knowledge_path):
    """Ensure accuralai-rag powered search returns results when enabled."""
    kb = KnowledgeBase(knowledge_path=knowledge_path, use_embeddings=True)
    await kb.initialize()

    results = await kb.search("parole", max_results=2)
    assert len(results) > 0
    assert all("full_content" in r for r in results)


def test_context7_search_instance():
    """Test Context7 search instance creation."""
    search = get_context7_search()
    assert search is not None
    assert hasattr(search, "search")
    assert hasattr(search, "clear_cache")


@pytest.mark.asyncio
async def test_context7_search(knowledge_path):
    """Test Context7 search (may return empty if MCP not configured)."""
    search = get_context7_search()
    result = await search.search("jail system")
    # Result may be empty if MCP not configured, which is OK
    assert isinstance(result, str)

