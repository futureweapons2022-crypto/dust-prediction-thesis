"""
Build RAG Vector Store — Anthropogenic Dust Sources
Extracts text from PDFs → chunks → embeds → stores in ChromaDB

Steps:
1. Extract text from PDFs using Docling (structure-aware)
2. Chunk by sections, then recursive split (~1000 chars, 200 overlap)
3. Embed using BAAI/bge-m3 (multilingual, 1024-dim)
4. Store in ChromaDB with metadata
5. Build BM25 index for hybrid search

Usage:
    python build_rag.py                  # Process all PDFs
    python build_rag.py --limit 10       # Process first 10 PDFs only (for testing)
    python build_rag.py --skip-embed     # Extract + chunk only (no embedding)
"""

import os
import sys
import json
import csv
import re
import time
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
PDF_DIR = BASE_DIR / "pdfs"
TEXT_DIR = BASE_DIR / "texts"
CHUNKS_DIR = BASE_DIR / "chunks"
VECTORDB_DIR = BASE_DIR / "vectordb"
BM25_PATH = BASE_DIR / "bm25_index.pkl"
METADATA_CSV = BASE_DIR / "papers_metadata.csv"

# Chunking config
CHUNK_SIZE = 1000       # characters
CHUNK_OVERLAP = 200     # characters
MIN_CHUNK_SIZE = 100    # skip tiny chunks

# Embedding config
EMBEDDING_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 8          # CPU-friendly batch size

# ChromaDB
COLLECTION_NAME = "thesis_rag"


# ============================================================
# STEP 1: PDF TEXT EXTRACTION
# ============================================================

def extract_texts(pdf_dir, text_dir, limit=None):
    """Extract text from PDFs using PyMuPDF (lightweight, no GPU/RAM issues)."""
    import fitz  # PyMuPDF

    text_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if limit:
        pdf_files = pdf_files[:limit]

    print(f"\nExtracting text from {len(pdf_files)} PDFs...")
    success = 0
    failed = 0

    for i, pdf_path in enumerate(pdf_files):
        txt_path = text_dir / (pdf_path.stem + ".md")

        # Skip if already extracted
        if txt_path.exists() and txt_path.stat().st_size > 0:
            success += 1
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(pdf_files)}] (skipped existing)")
            continue

        try:
            doc = fitz.open(str(pdf_path))
            pages_text = []

            for page_num, page in enumerate(doc):
                text = page.get_text("text")
                if text.strip():
                    pages_text.append(f"## Page {page_num + 1}\n\n{text}")

            doc.close()

            full_text = "\n\n".join(pages_text)

            if len(full_text.strip()) < 50:
                print(f"  [WARN] Near-empty extraction: {pdf_path.name}")
                failed += 1
                continue

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            success += 1

        except Exception as e:
            print(f"  [ERROR] {pdf_path.name}: {e}")
            failed += 1

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(pdf_files)}] ({success} ok, {failed} failed)")

    print(f"  Extraction done: {success} ok, {failed} failed")
    return success


# ============================================================
# STEP 2: CHUNKING
# ============================================================

def load_paper_metadata():
    """Load metadata from scraper CSV."""
    metadata = {}
    if not METADATA_CSV.exists():
        return metadata

    with open(METADATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = row.get("doi", "")
            if doi:
                # Map DOI-based filename to metadata
                safe_name = doi.replace("/", "_").replace(":", "_").replace("\\", "_")
                metadata[safe_name] = {
                    "doi": doi,
                    "title": row.get("title", ""),
                    "authors": row.get("authors", ""),
                    "year": row.get("year", ""),
                    "journal": row.get("journal", ""),
                }
    return metadata


def split_into_sections(text):
    """Split markdown text by section headers."""
    sections = []
    current_section = "Introduction"  # default for text before first header
    current_text = []

    for line in text.split("\n"):
        # Detect markdown headers
        header_match = re.match(r'^(#{1,4})\s+(.+)', line)
        if header_match:
            # Save previous section
            if current_text:
                content = "\n".join(current_text).strip()
                if len(content) >= MIN_CHUNK_SIZE:
                    sections.append((current_section, content))
            current_section = header_match.group(2).strip()
            current_text = []
        else:
            current_text.append(line)

    # Don't forget last section
    if current_text:
        content = "\n".join(current_text).strip()
        if len(content) >= MIN_CHUNK_SIZE:
            sections.append((current_section, content))

    # If no sections found (no headers), treat whole text as one section
    if not sections:
        sections = [("Full Text", text.strip())]

    return sections


def recursive_split(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Recursively split text into chunks, preferring natural boundaries."""
    if len(text) <= chunk_size:
        return [text] if len(text) >= MIN_CHUNK_SIZE else []

    chunks = []
    # Try splitting by paragraphs first, then sentences, then raw
    separators = ["\n\n", "\n", ". ", " "]

    for sep in separators:
        parts = text.split(sep)
        if len(parts) > 1:
            current_chunk = ""
            for part in parts:
                candidate = current_chunk + sep + part if current_chunk else part
                if len(candidate) <= chunk_size:
                    current_chunk = candidate
                else:
                    if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                        chunks.append(current_chunk.strip())
                    # Start new chunk with overlap
                    if overlap > 0 and current_chunk:
                        overlap_text = current_chunk[-overlap:]
                        current_chunk = overlap_text + sep + part
                    else:
                        current_chunk = part

            if current_chunk and len(current_chunk) >= MIN_CHUNK_SIZE:
                chunks.append(current_chunk.strip())

            if chunks:
                return chunks

    # Fallback: hard split by characters
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if len(chunk) >= MIN_CHUNK_SIZE:
            chunks.append(chunk.strip())

    return chunks


def chunk_all_texts(text_dir, chunks_dir):
    """Chunk all extracted texts."""
    chunks_dir.mkdir(parents=True, exist_ok=True)
    metadata = load_paper_metadata()

    text_files = sorted(text_dir.glob("*.md"))
    all_chunks = []

    print(f"\nChunking {len(text_files)} documents...")

    for i, txt_path in enumerate(text_files):
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()

        stem = txt_path.stem
        paper_meta = metadata.get(stem, {})

        # Split into sections
        sections = split_into_sections(text)

        # Chunk each section
        for section_name, section_text in sections:
            chunks = recursive_split(section_text)
            for j, chunk_text in enumerate(chunks):
                chunk_id = f"{stem}__s{section_name[:30]}__c{j}"
                all_chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "source_file": stem,
                    "section": section_name,
                    "chunk_index": j,
                    "doi": paper_meta.get("doi", ""),
                    "title": paper_meta.get("title", ""),
                    "authors": paper_meta.get("authors", ""),
                    "year": paper_meta.get("year", ""),
                    "journal": paper_meta.get("journal", ""),
                })

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(text_files)}] ({len(all_chunks)} chunks so far)")

    # Save chunks to JSON for inspection
    chunks_file = chunks_dir / "all_chunks.json"
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"  Chunking done: {len(all_chunks)} chunks from {len(text_files)} papers")
    print(f"  Saved to: {chunks_file}")
    return all_chunks


# ============================================================
# STEP 3: EMBEDDING + VECTOR STORE
# ============================================================

def build_vector_store(chunks):
    """Embed chunks and store in ChromaDB."""
    from FlagEmbedding import BGEM3FlagModel
    import chromadb

    print(f"\nLoading embedding model: {EMBEDDING_MODEL}...")
    model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)  # CPU mode

    print(f"Embedding {len(chunks)} chunks (batch_size={BATCH_SIZE})...")
    print("  This will take a while on CPU. Progress updates every 50 batches.")

    # Extract texts for embedding
    texts = [c["text"] for c in chunks]

    # Embed in batches
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        embeddings = model.encode(
            batch,
            batch_size=BATCH_SIZE,
            max_length=1024,  # Limit to save memory on CPU
        )
        all_embeddings.extend(embeddings["dense_vecs"].tolist())

        if ((i // BATCH_SIZE) + 1) % 50 == 0:
            elapsed_pct = (i + BATCH_SIZE) / len(texts) * 100
            print(f"  {elapsed_pct:.0f}% ({i + BATCH_SIZE}/{len(texts)} chunks embedded)")

    print("  Embedding complete. Storing in ChromaDB...")

    # Store in ChromaDB
    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTORDB_DIR))

    # Delete existing collection if it exists
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # Add in batches (ChromaDB has a limit)
    chroma_batch = 500
    for i in range(0, len(chunks), chroma_batch):
        batch_chunks = chunks[i:i + chroma_batch]
        batch_embeddings = all_embeddings[i:i + chroma_batch]

        collection.add(
            ids=[c["id"] for c in batch_chunks],
            embeddings=batch_embeddings,
            documents=[c["text"] for c in batch_chunks],
            metadatas=[{
                "doi": c["doi"],
                "title": c["title"],
                "authors": c["authors"],
                "year": str(c["year"]),
                "journal": c["journal"],
                "section": c["section"],
                "source_file": c["source_file"],
            } for c in batch_chunks],
        )

    print(f"  ChromaDB: {collection.count()} chunks stored in {VECTORDB_DIR}")
    return collection


# ============================================================
# STEP 4: BM25 INDEX
# ============================================================

def build_bm25_index(chunks):
    """Build BM25 index for keyword search."""
    from rank_bm25 import BM25Okapi

    print("\nBuilding BM25 index...")

    # Tokenize (simple whitespace + lowercase)
    tokenized = [c["text"].lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)

    # Save BM25 index + chunk IDs
    bm25_data = {
        "bm25": bm25,
        "chunk_ids": [c["id"] for c in chunks],
        "chunk_texts": [c["text"] for c in chunks],
    }
    with open(BM25_PATH, "wb") as f:
        pickle.dump(bm25_data, f)

    print(f"  BM25 index saved to: {BM25_PATH}")
    return bm25


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Build RAG vector store")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of PDFs to process")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding (extract + chunk only)")
    parser.add_argument("--chunks-only", action="store_true", help="Skip extraction, only chunk existing texts")
    args = parser.parse_args()

    start_time = time.time()

    # Step 1: Extract text from PDFs
    if not args.chunks_only:
        extract_texts(PDF_DIR, TEXT_DIR, limit=args.limit)

    # Step 2: Chunk texts
    chunks = chunk_all_texts(TEXT_DIR, CHUNKS_DIR)

    if not chunks:
        print("\nNo chunks produced. Check if PDFs were extracted correctly.")
        return

    # Step 3: Build BM25 index (fast, always do this)
    build_bm25_index(chunks)

    # Step 4: Embed and store in ChromaDB
    if not args.skip_embed:
        build_vector_store(chunks)
    else:
        print("\nSkipped embedding (--skip-embed). Run without flag to embed.")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"Papers processed: {len(list(TEXT_DIR.glob('*.md')))}")
    print(f"Chunks created:   {len(chunks)}")
    print(f"Time elapsed:     {elapsed/60:.1f} minutes")
    print(f"Vector DB:        {VECTORDB_DIR}")
    print(f"BM25 index:       {BM25_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
