"""
Query RAG System — Anthropogenic Dust Sources
Asks questions → hybrid search (vector + BM25) → rerank → LLM answer with citations

Usage:
    python query_rag.py "What caused increased dust in southern Iraq after 2000?"
    python query_rag.py --interactive     # Interactive mode (keep asking questions)
    python query_rag.py --retrieve-only "query"  # Show retrieved chunks without LLM
"""

import os
import sys
import json
import pickle
import argparse
from pathlib import Path

# Fix Windows Unicode
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data\rag_docs")
VECTORDB_DIR = BASE_DIR / "vectordb"
BM25_PATH = BASE_DIR / "bm25_index.pkl"
CHUNKS_FILE = BASE_DIR / "chunks" / "all_chunks.json"

COLLECTION_NAME = "thesis_rag"
EMBEDDING_MODEL = "BAAI/bge-m3"

# Retrieval config
TOP_K_VECTOR = 20       # Retrieve top 20 from vector search
TOP_K_BM25 = 20         # Retrieve top 20 from BM25
TOP_K_RERANK = 10       # Rerank to top 10
TOP_K_FINAL = 5         # Send top 5 to LLM

# LLM config (Gemini — free)
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


# ============================================================
# LOAD INDICES (one-time)
# ============================================================

_model = None
_collection = None
_bm25_data = None
_chunks = None
_reranker = None


def load_all():
    """Load all indices and models."""
    global _model, _collection, _bm25_data, _chunks, _reranker

    if _model is not None:
        return  # Already loaded

    print("Loading models and indices...")

    # Load embedding model
    from FlagEmbedding import BGEM3FlagModel
    print("  Loading embedding model...")
    _model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)

    # Load ChromaDB
    import chromadb
    print("  Loading ChromaDB...")
    client = chromadb.PersistentClient(path=str(VECTORDB_DIR))
    _collection = client.get_collection(COLLECTION_NAME)
    print(f"  ChromaDB: {_collection.count()} chunks loaded")

    # Load BM25
    print("  Loading BM25 index...")
    with open(BM25_PATH, "rb") as f:
        _bm25_data = pickle.load(f)

    # Load chunks for metadata
    print("  Loading chunk metadata...")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks_list = json.load(f)
    _chunks = {c["id"]: c for c in chunks_list}

    # Load reranker
    from flashrank import Ranker
    print("  Loading FlashRank reranker...")
    _reranker = Ranker()

    print("  All loaded. Ready to query.\n")


# ============================================================
# RETRIEVAL
# ============================================================

def vector_search(query, top_k=TOP_K_VECTOR):
    """Semantic search via ChromaDB."""
    # Embed the query
    query_embedding = _model.encode(
        [query],
        max_length=512,
    )["dense_vecs"][0].tolist()

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],  # cosine distance → similarity
            "source": "vector",
        })
    return hits


def bm25_search(query, top_k=TOP_K_BM25):
    """Keyword search via BM25."""
    tokens = query.lower().split()
    scores = _bm25_data["bm25"].get_scores(tokens)

    # Get top-k indices
    import numpy as np
    top_indices = np.argsort(scores)[::-1][:top_k]

    hits = []
    for idx in top_indices:
        if scores[idx] > 0:
            chunk_id = _bm25_data["chunk_ids"][idx]
            chunk_text = _bm25_data["chunk_texts"][idx]
            meta = _chunks.get(chunk_id, {})
            hits.append({
                "id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    "doi": meta.get("doi", ""),
                    "title": meta.get("title", ""),
                    "year": str(meta.get("year", "")),
                    "journal": meta.get("journal", ""),
                    "section": meta.get("section", ""),
                },
                "score": float(scores[idx]),
                "source": "bm25",
            })
    return hits


def hybrid_search(query):
    """Combine vector + BM25 results."""
    vector_hits = vector_search(query)
    bm25_hits = bm25_search(query)

    # Merge by chunk ID, keeping best score
    seen = {}
    for hit in vector_hits:
        seen[hit["id"]] = hit
        seen[hit["id"]]["sources"] = ["vector"]

    for hit in bm25_hits:
        if hit["id"] in seen:
            seen[hit["id"]]["sources"].append("bm25")
            # Boost score for chunks found by BOTH methods
            seen[hit["id"]]["score"] *= 1.2
        else:
            hit["sources"] = ["bm25"]
            seen[hit["id"]] = hit

    # Sort by score
    merged = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return merged[:TOP_K_RERANK * 2]  # Give reranker more candidates


def rerank(query, hits, top_k=TOP_K_RERANK):
    """Rerank hits using FlashRank cross-encoder."""
    from flashrank import RerankRequest

    if not hits:
        return []

    # Prepare for reranking
    passages = [{"id": h["id"], "text": h["text"], "meta": h.get("metadata", {})} for h in hits]
    request = RerankRequest(query=query, passages=passages)
    results = _reranker.rerank(request)

    # Map back to our format
    reranked = []
    hit_map = {h["id"]: h for h in hits}
    for r in results[:top_k]:
        hit = hit_map.get(r["id"], {})
        hit["rerank_score"] = r["score"]
        reranked.append(hit)

    return reranked


# ============================================================
# LLM GENERATION
# ============================================================

def generate_answer(query, context_chunks):
    """Send query + context to Gemini for a cited answer."""
    import requests

    # Build context string
    context_parts = []
    for i, chunk in enumerate(context_chunks[:TOP_K_FINAL]):
        meta = chunk.get("metadata", {})
        source_info = f"[{i+1}] {meta.get('title', 'Unknown')} ({meta.get('year', '?')}) - {meta.get('journal', '')}"
        context_parts.append(f"{source_info}\n{chunk['text']}\n")

    context = "\n---\n".join(context_parts)

    prompt = f"""You are a research assistant analyzing academic literature about dust emissions,
land degradation, and anthropogenic dust sources in the Middle East and Arabian Gulf region.

Based ONLY on the provided source documents below, answer the following question.
For each claim, cite the source using [1], [2], etc.
If the sources don't contain enough information, say so explicitly.

SOURCES:
{context}

QUESTION: {query}

ANSWER (with citations):"""

    # Call Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000,
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"]
        return answer
    except Exception as e:
        return f"[LLM Error: {e}]"


# ============================================================
# DISPLAY
# ============================================================

def display_results(query, chunks, answer=None):
    """Pretty-print results."""
    print(f"\n{'='*70}")
    print(f"QUERY: {query}")
    print(f"{'='*70}")

    print(f"\nTop {len(chunks)} retrieved chunks:")
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        sources = chunk.get("sources", [chunk.get("source", "?")])
        score = chunk.get("rerank_score", chunk.get("score", 0))
        print(f"\n  [{i+1}] Score: {score:.3f} | Via: {'+'.join(sources)}")
        print(f"      Paper: {meta.get('title', 'Unknown')[:80]}")
        print(f"      Year: {meta.get('year', '?')} | Section: {meta.get('section', '?')[:40]}")
        print(f"      Text: {chunk['text'][:200]}...")

    if answer:
        print(f"\n{'='*70}")
        print(f"ANSWER:")
        print(f"{'='*70}")
        print(answer)

    # Print source list
    print(f"\n{'='*70}")
    print("SOURCES:")
    seen_dois = set()
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})
        doi = meta.get("doi", "")
        if doi and doi not in seen_dois:
            seen_dois.add(doi)
            print(f"  [{i+1}] {meta.get('title', 'Unknown')[:70]} ({meta.get('year', '?')})")
            print(f"      DOI: {doi}")
    print(f"{'='*70}\n")


# ============================================================
# MAIN
# ============================================================

def process_query(query, retrieve_only=False):
    """Full RAG pipeline for one query."""
    # Step 1: Hybrid search
    hits = hybrid_search(query)

    # Step 2: Rerank
    reranked = rerank(query, hits)

    # Step 3: Generate answer (unless retrieve-only)
    answer = None
    if not retrieve_only:
        answer = generate_answer(query, reranked)

    # Display
    display_results(query, reranked, answer)

    return reranked, answer


def main():
    parser = argparse.ArgumentParser(description="Query RAG system")
    parser.add_argument("query", nargs="?", default=None, help="Question to ask")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--retrieve-only", action="store_true", help="No LLM, just show chunks")
    args = parser.parse_args()

    load_all()

    if args.interactive or args.query is None:
        print("Interactive RAG Query Mode. Type 'quit' to exit.\n")
        while True:
            try:
                query = input("Question: ").strip()
                if query.lower() in ("quit", "exit", "q"):
                    break
                if not query:
                    continue
                process_query(query, retrieve_only=args.retrieve_only)
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        print("\nGoodbye.")
    else:
        process_query(args.query, retrieve_only=args.retrieve_only)


if __name__ == "__main__":
    main()
