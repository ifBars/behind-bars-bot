# Embedding Configuration Guide

## Overview

Behind Bars now relies on the `accuralai-rag` package for semantic search. The retriever chunks every markdown guide, generates multi-vector embeddings locally, and feeds them to a hybrid dense + sparse index. No remote embedding APIs are called, so there are no rate limits or `.embeddings_cache` directories to manage.

## How accuralai-rag Handles Embeddings

- **Local models by default** – If `sentence-transformers` is available the retriever loads `BAAI/bge-large-en-v1.5`. When that dependency is missing it falls back to a lightweight hashed representation so the bot can still run on minimal installs.
- **Automatic sparse metadata** – Keyword weights are produced next to the dense vectors, enabling BM25-style retrieval without additional configuration.
- **In-memory caching** – All vectors live in memory for the process lifetime. Restarting the bot simply re-encodes the documents, which usually takes a few seconds because everything is computed locally.

## Tuning Chunking and Index Size

- `chunk_size` and `chunk_overlap` in `bot.py` map to the chunker's token window (roughly `chunk_size / 4` words). Larger windows create fewer chunks at startup; smaller windows improve recall for terse topics.
- The index stores metadata for every chunk, so adding markdown files under `knowledge/` automatically makes them searchable—no manual cache clearing needed.
- Installing optional dependencies such as `sentence-transformers` or `faiss` unlocks GPU acceleration and ANN search automatically.

## Disabling Semantic Search

The legacy keyword fallback still exists for ultra-low-resource deployments. Disable embeddings via the environment:

```bash
export BEHIND_BARS_DISABLE_EMBEDDINGS=true
```

or add `BEHIND_BARS_DISABLE_EMBEDDINGS=true` to `.env`. When disabled, the bot skips accuralai-rag entirely and performs straightforward keyword matching.

## Troubleshooting

- **Slow startup** – Reduce the number of knowledge documents or increase `chunk_size` so there are fewer chunks to encode.
- **Higher memory usage** – Larger chunk sizes create fewer vectors. You can also disable embeddings to fall back to keyword search.
- **Missing matches** – Install `sentence-transformers` for high-quality dense embeddings or confirm that your new markdown files live inside the `knowledge/` directory.

## Monitoring

Look for these log lines:
- `Registered X chunks with accuralai-rag` – semantic index ready.
- `RAG index not ready, using keyword fallback` – embeddings were disabled or initialization failed.
- `Dense embeddings unavailable; disabling embedding search` – install `sentence-transformers` if you need higher recall.
