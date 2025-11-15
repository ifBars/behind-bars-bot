"""GitHub README fetcher with RAG support for Behind Bars repository."""

from __future__ import annotations

import asyncio
import logging
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

# GitHub raw URL for Behind Bars README
GITHUB_README_URL = "https://raw.githubusercontent.com/SirTidez/Behind-Bars/refs/heads/master/README.md"


class GitHubReadmeFetcher:
    """Fetcher for Behind Bars GitHub README with RAG support."""

    def __init__(
        self,
        embedding_model: str = "BAAI/bge-large-en-v1.5",
        chunk_size: int = 2000,
        chunk_overlap: int = 300,
    ):
        """Initialize GitHub README fetcher with RAG."""
        self._cache: Optional[str] = None
        self._cache_enabled = True
        self._http_client: Optional[aiohttp.ClientSession] = None
        
        # RAG components
        self._rag_ready = False
        self._building_index = False
        self._chunks: List[DocumentChunk] = []
        self._search_engine: Optional[HybridSearchEngine] = None
        self._query_optimizer = QueryOptimizer()
        
        # Chunking configuration
        token_chunk_size = max(128, chunk_size // 4)
        token_overlap = max(32, chunk_overlap // 4)
        self._chunker = SmartChunker(
            chunk_size=token_chunk_size,
            overlap=token_overlap,
            chunk_id_prefix="github-readme",
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

    async def fetch_readme(self, use_cache: bool = True) -> str:
        """
        Fetch the latest Behind Bars README from GitHub.

        Args:
            use_cache: Whether to use cached result if available

        Returns:
            README content from GitHub
        """
        # Check cache first
        if use_cache and self._cache_enabled and self._cache is not None:
            LOGGER.debug("Returning cached GitHub README")
            return self._cache

        try:
            client = await self._get_http_client()
            if client is None:
                LOGGER.error("HTTP client not available")
                return ""

            LOGGER.debug(f"Fetching GitHub README from: {GITHUB_README_URL}")

            # Make HTTP request using aiohttp (persistent session)
            async with client.get(GITHUB_README_URL) as response:
                response.raise_for_status()
                content = await response.text()

            # Check if content changed before caching
            content_changed = self._cache != content
            
            # Cache the result
            if self._cache_enabled:
                self._cache = content
                LOGGER.debug(f"Cached GitHub README ({len(content)} chars)")

            LOGGER.info(f"Fetched GitHub README ({len(content)} chars)")
            
            # Rebuild RAG index if content changed or not ready
            if content_changed or not self._rag_ready:
                await self._ensure_rag_ready(content)
            
            return content

        except aiohttp.ClientError as e:
            LOGGER.error(f"HTTP error fetching GitHub README: {e}", exc_info=True)
            return ""
        except Exception as e:
            LOGGER.error(f"Error fetching GitHub README: {e}", exc_info=True)
            return ""

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the GitHub README using RAG.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of search results with relevant chunks
        """
        if not query or not query.strip():
            return []

        # Ensure README is fetched and indexed
        readme_content = await self.fetch_readme()
        if not readme_content:
            return []

        await self._ensure_rag_ready(readme_content)

        if not self._rag_ready or not self._search_engine:
            LOGGER.debug("RAG index not ready, falling back to keyword search")
            return self._search_keyword(query, readme_content, max_results)

        try:
            return await self._rag_search(query, max_results)
        except Exception as exc:
            LOGGER.warning(f"RAG search failed ({exc}), falling back to keyword search", exc_info=True)
            return self._search_keyword(query, readme_content, max_results)

    async def _ensure_rag_ready(self, content: str) -> None:
        """Ensure RAG index is built for the README content."""
        if self._building_index:
            return

        loop = asyncio.get_event_loop()
        self._building_index = True
        try:
            await loop.run_in_executor(None, self._build_rag_index, content)
        finally:
            self._building_index = False

    def _build_rag_index(self, content: str) -> None:
        """Build RAG index from README content."""
        if not content:
            return

        LOGGER.info("Building RAG index for GitHub README")

        # Chunk the README
        metadata = {
            "source": "github",
            "path": "README.md",
            "type": "readme",
        }
        chunks = self._chunker.chunk_document(content, metadata=metadata)

        if not chunks:
            LOGGER.warning("No chunks generated for GitHub README")
            return

        # Generate embeddings
        embeddings = self._retriever.encode_documents([chunk.text for chunk in chunks])
        dense_value = embeddings.get("dense")
        dense_embeddings = list(dense_value) if dense_value is not None else []
        
        if not dense_embeddings:
            LOGGER.warning("Dense embeddings unavailable for GitHub README")
            return

        sparse_embeddings = embeddings.get("sparse")
        dimension = len(dense_embeddings[0])
        
        # Always create a new search engine when rebuilding the index
        # (HybridSearchEngine doesn't have a clear method, so we recreate it)
        self._search_engine = HybridSearchEngine(dimension=dimension)

        self._chunks = chunks
        self._search_engine.add_documents(
            chunks,
            dense_embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
        )
        self._rag_ready = True
        LOGGER.info(f"Registered {len(chunks)} chunks from GitHub README with RAG")

    async def _rag_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform RAG search on the README."""
        if not self._search_engine:
            return []

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
            
            results = self._search_engine.search(
                variation,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                k=search_k,
                final_k=max_results,
            )
            aggregated.extend(results)

        deduped = self._deduplicate_results(aggregated)
        limited = deduped[:max_results]
        return [self._format_result(result, query) for result in limited]

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

    def _format_result(self, result: RetrievalResult, query: str) -> Dict[str, Any]:
        """Format a search result."""
        metadata = dict(result.chunk.metadata)
        snippet = self._extract_snippet(result.chunk.text, query)
        return {
            "path": metadata.get("path", "README.md"),
            "type": metadata.get("type", "readme"),
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
                    "path": "README.md",
                    "type": "readme",
                    "snippet": snippet,
                    "score": score,
                    "full_content": content[:2000],
                    "metadata": {"source": "github"},
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
        """Clear the cached README and RAG index."""
        self._cache = None
        self._rag_ready = False
        self._chunks = []
        self._search_engine = None
        LOGGER.debug("GitHub README cache and RAG index cleared")

    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching."""
        self._cache_enabled = enabled


# Global instance
_github_readme_fetcher: Optional[GitHubReadmeFetcher] = None


def get_github_readme_fetcher() -> GitHubReadmeFetcher:
    """Get or create global GitHub README fetcher instance."""
    global _github_readme_fetcher
    if _github_readme_fetcher is None:
        _github_readme_fetcher = GitHubReadmeFetcher()
    return _github_readme_fetcher

