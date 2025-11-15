"""Context7 integration for Behind Bars documentation search with RAG support."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence

import aiohttp
from accuralai_rag import (
    DocumentChunk,
    HybridSearchEngine,
    MultiVectorRetriever,
    QueryOptimizer,
    RetrievalResult,
    SmartChunker,
)

LOGGER = logging.getLogger("behind_bars_bot")

# Context7 base URL for Behind Bars
CONTEXT7_BASE_URL = "https://context7.com/sirtidez/behind-bars/llms.txt"


class Context7Search:
    """Wrapper for Context7 to fetch Behind Bars documentation with RAG support."""

    def __init__(
        self,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        chunk_size: int = 2000,
        chunk_overlap: int = 300,
    ):
        """Initialize Context7 search with RAG."""
        self._cache: Dict[str, str] = {}
        self._cache_enabled = True
        self._http_client: Optional[aiohttp.ClientSession] = None
        
        # RAG components - separate index per topic
        self._rag_indices: Dict[str, Dict[str, Any]] = {}  # topic -> {engine, chunks, ready}
        self._building_index: Dict[str, bool] = {}  # topic -> building flag
        self._query_optimizer = QueryOptimizer()
        
        # Chunking configuration
        token_chunk_size = max(128, chunk_size // 4)
        token_overlap = max(32, chunk_overlap // 4)
        self._chunker = SmartChunker(
            chunk_size=token_chunk_size,
            overlap=token_overlap,
            chunk_id_prefix="context7",
        )
        self._retriever = MultiVectorRetriever(dense_model_name=embedding_model)

    async def _get_http_client(self) -> Optional[aiohttp.ClientSession]:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.closed:
            self._http_client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.closed:
            await self._http_client.close()

    async def fetch(
        self,
        topic: Optional[str] = None,
        tokens: int = 10000,
        use_cache: bool = True,
    ) -> str:
        """
        Fetch Behind Bars documentation from Context7.

        Args:
            topic: Optional topic to search for (used in URL parameter)
            tokens: Maximum tokens to retrieve (used as URL parameter)
            use_cache: Whether to use cached result if available

        Returns:
            Documentation content from Context7
        """
        # Create cache key based on topic and tokens
        cache_key = f"context7:{topic or 'default'}:{tokens}"
        
        # Check cache first
        if use_cache and self._cache_enabled and cache_key in self._cache:
            LOGGER.debug(f"Returning cached Context7 result (topic: {topic}, tokens: {tokens})")
            return self._cache[cache_key]

        try:
            client = await self._get_http_client()
            if client is None:
                LOGGER.error("HTTP client not available")
                return ""

            # Build URL with topic and tokens parameters
            params = {"tokens": str(tokens)}
            if topic:
                params["topic"] = topic
            
            # URL encode the parameters
            query_string = urllib.parse.urlencode(params)
            url = f"{CONTEXT7_BASE_URL}?{query_string}"
            
            LOGGER.debug(f"Fetching Context7 documentation from: {url}")
            
            # Make HTTP request using aiohttp (persistent session)
            async with client.get(url) as response:
                response.raise_for_status()
                content = await response.text()
            
            # Check if content changed before caching
            content_changed = self._cache.get(cache_key) != content
            
            # Cache the result
            if self._cache_enabled:
                self._cache[cache_key] = content
                LOGGER.debug(f"Cached Context7 result ({len(content)} chars)")
            
            LOGGER.info(f"Fetched Context7 documentation (topic: {topic}, {len(content)} chars)")
            
            # Build RAG index if content changed or not ready
            topic_key = topic or "default"
            if content_changed or topic_key not in self._rag_indices or not self._rag_indices[topic_key].get("ready", False):
                await self._ensure_rag_ready(content, topic_key)
            
            return content

        except aiohttp.ClientError as e:
            LOGGER.error(f"HTTP error fetching Context7 documentation: {e}", exc_info=True)
            return ""
        except Exception as e:
            LOGGER.error(f"Error fetching Context7 documentation: {e}", exc_info=True)
            return ""

    async def search(
        self,
        query: str,
        topic: Optional[str] = None,
        tokens: int = 10000,
        max_results: int = 5,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search Behind Bars documentation from Context7 using RAG.

        Args:
            query: Search query for semantic search
            topic: Optional topic to fetch from Context7 (used in URL parameter)
            tokens: Maximum tokens to retrieve from Context7
            max_results: Maximum number of results to return
            use_cache: Whether to use cached content if available

        Returns:
            List of search results with relevant chunks
        """
        if not query or len(query.strip()) < 2:
            return []

        # Fetch content from Context7 with topic parameter
        content = await self.fetch(topic=topic, tokens=tokens, use_cache=use_cache)
        if not content:
            return []

        topic_key = topic or "default"
        await self._ensure_rag_ready(content, topic_key)

        rag_index = self._rag_indices.get(topic_key)
        if not rag_index or not rag_index.get("ready", False) or not rag_index.get("engine"):
            LOGGER.debug("RAG index not ready, falling back to keyword search")
            return self._search_keyword(query, content, max_results)

        try:
            return await self._rag_search(query, topic_key, max_results)
        except Exception as exc:
            LOGGER.warning(f"RAG search failed ({exc}), falling back to keyword search", exc_info=True)
            return self._search_keyword(query, content, max_results)

    async def _ensure_rag_ready(self, content: str, topic_key: str) -> None:
        """Ensure RAG index is built for the content."""
        if topic_key in self._building_index and self._building_index[topic_key]:
            return

        loop = asyncio.get_event_loop()
        self._building_index[topic_key] = True
        try:
            await loop.run_in_executor(None, self._build_rag_index, content, topic_key)
        finally:
            self._building_index[topic_key] = False

    def _build_rag_index(self, content: str, topic_key: str) -> None:
        """Build RAG index from Context7 content."""
        if not content:
            return

        LOGGER.info(f"Building RAG index for Context7 topic: {topic_key}")

        # Chunk the content
        metadata = {
            "source": "context7",
            "topic": topic_key,
            "type": "documentation",
        }
        chunks = self._chunker.chunk_document(content, metadata=metadata)

        if not chunks:
            LOGGER.warning(f"No chunks generated for Context7 topic: {topic_key}")
            return

        # Generate embeddings
        embeddings = self._retriever.encode_documents([chunk.text for chunk in chunks])
        dense_value = embeddings.get("dense")
        dense_embeddings = list(dense_value) if dense_value is not None else []
        
        if not dense_embeddings:
            LOGGER.warning(f"Dense embeddings unavailable for Context7 topic: {topic_key}")
            return

        sparse_embeddings = embeddings.get("sparse")
        dimension = len(dense_embeddings[0])
        
        # Always create a new search engine when rebuilding the index
        search_engine = HybridSearchEngine(dimension=dimension)
        search_engine.add_documents(
            chunks,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
        )

        # Store the index
        self._rag_indices[topic_key] = {
            "engine": search_engine,
            "chunks": chunks,
            "ready": True,
        }
        
        LOGGER.info(f"Registered {len(chunks)} chunks from Context7 topic '{topic_key}' with RAG")

    async def _rag_search(self, query: str, topic_key: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform RAG search on the Context7 content."""
        rag_index = self._rag_indices.get(topic_key)
        if not rag_index or not rag_index.get("engine"):
            return []

        search_engine = rag_index["engine"]
        variations = await self._query_optimizer.enhance_query(query)
        aggregated: List[RetrievalResult] = []
        search_k = max(25, max_results)

        for variation in variations:
            encoded = self._retriever.encode_queries([variation])
            dense_value = encoded.get("dense")
            sparse_value = encoded.get("sparse")
            dense_vecs = list(dense_value) if dense_value is not None else []
            sparse_vecs = list(sparse_value) if sparse_value is not None else []
            dense_vector = dense_vecs[0] if dense_vecs else None
            sparse_vector = sparse_vecs[0] if sparse_vecs else None
            
            results = search_engine.search(
                variation,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                k=search_k,
                final_k=max_results,
            )
            aggregated.extend(results)

        deduped = self._deduplicate_results(aggregated)
        limited = deduped[:max_results]
        return [self._format_result(result, query, topic_key) for result in limited]

    def _deduplicate_results(self, results: Sequence[RetrievalResult]) -> List[RetrievalResult]:
        """Deduplicate search results."""
        deduped: Dict[str, RetrievalResult] = {}
        for result in results:
            chunk = result.chunk
            fingerprint = chunk.fingerprint or chunk.chunk_id
            existing = deduped.get(fingerprint)
            if existing is None or result.score > existing.score:
                deduped[fingerprint] = result
        ordered = sorted(deduped.values(), key=lambda res: res.score, reverse=True)
        return ordered

    def _format_result(self, result: RetrievalResult, query: str, topic_key: str) -> Dict[str, Any]:
        """Format a search result."""
        metadata = dict(result.chunk.metadata)
        snippet = self._extract_snippet(result.chunk.text, query)
        return {
            "path": metadata.get("topic", topic_key),
            "type": metadata.get("type", "documentation"),
            "snippet": snippet,
            "score": float(result.score),
            "full_content": result.chunk.text,
            "metadata": metadata,
        }

    def _search_keyword(self, query: str, content: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback keyword search."""
        query_lower = query.lower()
        query_terms = query_lower.split()
        content_lower = content.lower()

        # Simple scoring based on term matches
        score = 0
        if query_lower in content_lower:
            score += 10
        score += sum(content_lower.count(term) for term in query_terms)

        if score > 0:
            snippet = self._extract_snippet(content, query_lower)
            return [
                {
                    "path": "Context7",
                    "type": "documentation",
                    "snippet": snippet,
                    "score": score,
                    "full_content": content[:2000],
                    "metadata": {"source": "context7"},
                }
            ]
        return []

    @staticmethod
    def _extract_snippet(content: str, query: str, context_lines: int = 3) -> str:
        """Extract a snippet around the query match."""
        content_lower = content.lower()
        query_lower = query.lower()
        idx = content_lower.find(query_lower)
        
        if idx == -1:
            return "\n".join(content.split("\n")[:5])

        lines = content.split("\n")
        line_idx = content[:idx].count("\n")
        start = max(0, line_idx - context_lines)
        end = min(len(lines), line_idx + context_lines + 1)
        snippet_lines = lines[start:end]
        snippet = "\n".join(snippet_lines)
        
        if len(snippet) < 500:
            return snippet
        return snippet[:500] + "..."

    def clear_cache(self) -> None:
        """Clear the Context7 result cache and RAG indices."""
        self._cache.clear()
        self._rag_indices.clear()
        self._building_index.clear()
        LOGGER.debug("Context7 cache and RAG indices cleared")

    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching."""
        self._cache_enabled = enabled


# Global instance
_context7_search: Optional[Context7Search] = None


def get_context7_search() -> Context7Search:
    """Get or create global Context7 search instance."""
    global _context7_search
    if _context7_search is None:
        _context7_search = Context7Search()
    return _context7_search

