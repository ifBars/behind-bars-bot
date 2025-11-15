"""Local knowledge base backed by the accuralai-rag package."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from accuralai_rag import (
    DocumentChunk,
    HybridSearchEngine,
    MultiVectorRetriever,
    QueryOptimizer,
    SmartChunker,
    RetrievalResult,
)

LOGGER = logging.getLogger("behind_bars_bot")


class KnowledgeBase:
    """Knowledge base for Behind Bars documentation powered by accuralai-rag."""

    def __init__(
        self,
        knowledge_path: str | Path,
        use_embeddings: bool = True,
        embedding_api_key: Optional[str] = None,  # Deprecated: retained for compatibility
        embedding_model: str = "BAAI/bge-large-en-v1.5",
        embedding_cache_path: Optional[str | Path] = None,  # Deprecated cache hint
        chunk_size: int = 2000,
        chunk_overlap: int = 300,
    ) -> None:
        self.knowledge_path = Path(knowledge_path)
        if embedding_api_key:
            LOGGER.debug("embedding_api_key parameter is ignored; accuralai-rag runs locally")
        if embedding_cache_path:
            LOGGER.debug("embedding_cache_path parameter is ignored; accuralai-rag handles caching in-memory")
        self.use_embeddings = use_embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.index: List[Dict[str, Any]] = []
        self._initialized = False
        self._rag_ready = False
        self._building_index = False
        self._chunks: List[DocumentChunk] = []
        self._search_engine: Optional[HybridSearchEngine] = None
        self._query_optimizer = QueryOptimizer()

        token_chunk_size = max(128, chunk_size // 4)
        token_overlap = max(32, chunk_overlap // 4)
        self._chunker = SmartChunker(
            chunk_size=token_chunk_size,
            overlap=token_overlap,
            chunk_id_prefix="behind-bars",
        )
        self._retriever = MultiVectorRetriever(dense_model_name=embedding_model)

    async def initialize(self) -> None:
        """Load markdown documents and build the searchable index."""
        if self._initialized:
            return

        LOGGER.info("Initializing knowledge base from %s", self.knowledge_path)

        if not self.knowledge_path.exists():
            LOGGER.warning("Knowledge path does not exist: %s", self.knowledge_path)
            self._initialized = True
            return

        indexed_files: List[Dict[str, Any]] = []
        for md_file in self.knowledge_path.glob("*.md"):
            try:
                content = await self._read_file_async(md_file)
            except Exception as exc:  # pragma: no cover - logged for diagnostics
                LOGGER.debug("Failed to read %s: %s", md_file, exc)
                continue

            if not content:
                continue

            indexed_files.append(
                {
                    "path": md_file.name,
                    "content": content,
                    "type": "markdown",
                }
            )

        self.index = indexed_files
        self._initialized = True
        LOGGER.info("Indexed %d knowledge documents", len(self.index))

        if self.use_embeddings:
            await self._ensure_rag_ready()

    @staticmethod
    async def _read_file_async(file_path: Path) -> Optional[str]:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, file_path.read_text, "utf-8")
        except Exception as exc:  # pragma: no cover - filesystem errors
            LOGGER.debug("Error reading %s: %s", file_path, exc)
            return None

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        if not self._initialized:
            await self.initialize()

        if not self.index:
            return []

        if not self.use_embeddings:
            return self._search_keyword(query, max_results)

        await self._ensure_rag_ready()

        if not self._rag_ready or not self._search_engine:
            LOGGER.debug("RAG index not ready, using keyword fallback")
            return self._search_keyword(query, max_results)

        try:
            rag_results = await self._rag_search(query, max_results)
            if rag_results:
                return rag_results
        except Exception as exc:  # pragma: no cover - fall back gracefully
            LOGGER.warning("accualai-rag search failed (%s), falling back to keyword search", exc)

        return self._search_keyword(query, max_results)

    async def _ensure_rag_ready(self) -> None:
        if not self.use_embeddings or self._rag_ready or self._building_index or not self.index:
            return

        loop = asyncio.get_event_loop()
        self._building_index = True
        try:
            await loop.run_in_executor(None, self._build_rag_index)
        finally:
            self._building_index = False

    def _build_rag_index(self) -> None:
        if self._rag_ready or not self.use_embeddings:
            return

        chunks: List[DocumentChunk] = []
        for doc in self.index:
            metadata = {
                "path": doc["path"],
                "type": doc.get("type", "markdown"),
            }
            doc_chunks = self._chunker.chunk_document(doc["content"], metadata=metadata)
            chunks.extend(doc_chunks)

        if not chunks:
            LOGGER.warning("No chunks generated for accuralai-rag index")
            return

        embeddings = self._retriever.encode_documents([chunk.text for chunk in chunks])
        dense_value = embeddings.get("dense")
        dense_embeddings = list(dense_value) if dense_value is not None else []
        if not dense_embeddings:
            LOGGER.warning("Dense embeddings unavailable; disabling embedding search")
            self.use_embeddings = False
            return

        sparse_embeddings = embeddings.get("sparse")
        dimension = len(dense_embeddings[0])
        if self._search_engine is None or getattr(self._search_engine, "dimension", dimension) != dimension:
            self._search_engine = HybridSearchEngine(dimension=dimension)

        self._chunks = chunks
        self._search_engine.add_documents(chunks, dense_embeddings=dense_embeddings, sparse_embeddings=sparse_embeddings)
        self._rag_ready = True
        LOGGER.info("Registered %d chunks with accuralai-rag", len(chunks))

    async def _rag_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
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
        metadata = dict(result.chunk.metadata)
        path = metadata.get("path") or metadata.get("document") or result.chunk.chunk_id
        snippet = self._extract_snippet(result.chunk.text, query)
        return {
            "path": path,
            "type": metadata.get("type", "markdown"),
            "snippet": snippet,
            "score": float(result.score),
            "full_content": result.chunk.text,
            "metadata": metadata,
        }

    def _search_keyword(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        query_terms = query_lower.split()

        results: List[Dict[str, Any]] = []
        for doc in self.index:
            content = doc["content"].lower()
            path = doc["path"].lower()

            score = 0
            if query_lower in content:
                score += 10
            term_matches = sum(content.count(term) for term in query_terms)
            score += term_matches
            if any(term in path for term in query_terms):
                score += 5
            for line in doc["content"].split("\n")[:20]:
                if line.strip().startswith("#") and any(term in line.lower() for term in query_terms):
                    score += 3

            if score > 0:
                snippet = self._extract_snippet(doc["content"], query_lower)
                results.append(
                    {
                        "path": doc["path"],
                        "type": doc["type"],
                        "snippet": snippet,
                        "score": score,
                        "full_content": doc["content"][:2000],
                    }
                )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:max_results]

    @staticmethod
    def _extract_snippet(content: str, query: str, context_lines: int = 3) -> str:
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
