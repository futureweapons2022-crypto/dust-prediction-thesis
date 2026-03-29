"""
Paper Scraper for RAG System — Anthropogenic Dust Sources
Uses OpenAlex API (free, no key) + Unpaywall (free, needs email) to:
1. Search for papers by keyword
2. Follow citation chains (snowball)
3. Download open-access PDFs
4. Save metadata to CSV

Usage:
    python scrape_papers.py              # Run all seed queries
    python scrape_papers.py --download   # Also download available PDFs
    python scrape_papers.py --snowball   # Also follow citation chains
"""

import requests
import csv
import os
import sys
import time
import argparse
import re
import json
from pathlib import Path
from urllib.parse import quote

# Fix Windows console Unicode encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(r"C:\Users\LENOVO\Desktop\THESIS\data\rag_docs")
PDF_DIR = BASE_DIR / "pdfs"
METADATA_CSV = BASE_DIR / "papers_metadata.csv"
SEEN_FILE = BASE_DIR / "seen_dois.json"

# OpenAlex config
OPENALEX_API = "https://api.openalex.org"
MAILTO = "ikukash@sharjah.ac.ae"  # Polite pool (faster rate limits)

# Unpaywall config
UNPAYWALL_API = "https://api.unpaywall.org/v2"
UNPAYWALL_EMAIL = MAILTO

# Rate limiting
DELAY_BETWEEN_REQUESTS = 0.2  # seconds (OpenAlex allows 10/sec with mailto)

# Study domain keywords for relevance filtering
REGION_KEYWORDS = [
    "middle east", "arabian", "gulf", "persian gulf", "iraq", "kuwait",
    "saudi", "uae", "emirates", "iran", "qatar", "bahrain", "oman",
    "mesopotamia", "tigris", "euphrates", "shamal", "mena",
    "levant", "syria", "jordan", "dust belt", "saharan",
    "arid", "dryland", "desert", "rub al-khali", "nafud", "dahna",
    "urmia", "hamoun", "sistan", "khuzestan", "basra", "mosul",
]

# ============================================================
# SEED QUERIES
# ============================================================

SEED_QUERIES = [
    # Marsh drainage
    "Mesopotamian marshlands dust source",
    "Iraqi marshes drainage dust emissions",
    "southern Iraq dust source anthropogenic",
    "Hawizeh marsh dust storms",
    "Hammar marsh degradation dust",

    # Water/lake drying
    "Lake Urmia dust storms desiccation",
    "Tigris Euphrates water diversion dust",
    "dried lakes dust source Middle East",
    "GAP project Turkey dust Iraq",
    "Aral Sea dust emissions desiccation",

    # Agriculture/land degradation
    "Saudi Arabia agricultural abandonment dust",
    "land use change dust source Arabian Peninsula",
    "desertification dust Kuwait overgrazing",
    "land degradation dust emission MENA",
    "irrigation loss dust Middle East",

    # Anthropogenic dust general
    "anthropogenic dust emissions review global",
    "anthropogenic dust fraction satellite",
    "dust source attribution MODIS Middle East",
    "sand dust storms Arabian Gulf",
    "CAMS dust model evaluation Middle East",

    # Climate/CMIP6 dust
    "dust emission climate change projection",
    "CMIP6 dust aerosol optical depth",
    "dust trend Middle East satellite",
]


# ============================================================
# HELPERS
# ============================================================

def load_seen_dois():
    """Load already-processed DOIs to avoid duplicates."""
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_dois(seen):
    """Persist seen DOIs."""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def is_region_relevant(text):
    """Check if text mentions our study region."""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in REGION_KEYWORDS)


def clean_text(text):
    """Remove HTML tags and clean text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\n", " ").strip()
    return text


def safe_filename(doi):
    """Convert DOI to safe filename."""
    return doi.replace("/", "_").replace(":", "_").replace("\\", "_")


# ============================================================
# OPENALEX SEARCH
# ============================================================

def search_openalex(query, max_results=100):
    """Search OpenAlex for papers matching query."""
    papers = []
    page = 1
    per_page = 50
    collected = 0

    while collected < max_results:
        url = (
            f"{OPENALEX_API}/works?"
            f"search={quote(query)}"
            f"&per_page={per_page}&page={page}"
            f"&mailto={MAILTO}"
            f"&select=id,doi,title,authorships,publication_year,"
            f"primary_location,cited_by_count,abstract_inverted_index,"
            f"open_access,referenced_works,cited_by_api_url,type"
        )

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [ERROR] OpenAlex search failed: {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            paper = parse_openalex_work(work)
            if paper:
                papers.append(paper)
                collected += 1
                if collected >= max_results:
                    break

        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return papers


def parse_openalex_work(work):
    """Parse an OpenAlex work into our paper dict."""
    doi = work.get("doi", "")
    if doi:
        doi = doi.replace("https://doi.org/", "")

    if not doi:
        return None

    # Reconstruct abstract from inverted index
    abstract = ""
    inv_idx = work.get("abstract_inverted_index")
    if inv_idx:
        word_positions = []
        for word, positions in inv_idx.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join(w for _, w in word_positions)

    # Authors
    authors = []
    for authorship in work.get("authorships", [])[:10]:
        author = authorship.get("author", {})
        name = author.get("display_name", "")
        if name:
            authors.append(name)

    # Journal
    journal = ""
    loc = work.get("primary_location", {})
    if loc:
        source = loc.get("source") or {}
        journal = source.get("display_name", "")

    # Open access
    oa = work.get("open_access", {})
    oa_url = oa.get("oa_url", "")
    is_oa = oa.get("is_oa", False)

    return {
        "doi": doi,
        "title": clean_text(work.get("title", "")),
        "authors": "; ".join(authors),
        "year": work.get("publication_year", ""),
        "journal": journal,
        "abstract": clean_text(abstract[:1000]),  # Truncate long abstracts
        "cited_by_count": work.get("cited_by_count", 0),
        "is_oa": is_oa,
        "oa_url": oa_url,
        "pdf_url": "",  # Will be filled by Unpaywall
        "pdf_downloaded": False,
        "source_query": "",
        "openalex_id": work.get("id", ""),
        "referenced_works": work.get("referenced_works", []),
        "cited_by_api_url": work.get("cited_by_api_url", ""),
    }


# ============================================================
# UNPAYWALL — FIND FREE PDFS
# ============================================================

def check_unpaywall(doi):
    """Check Unpaywall for a free PDF of this DOI."""
    url = f"{UNPAYWALL_API}/{doi}?email={UNPAYWALL_EMAIL}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()

        # Best OA location
        best = data.get("best_oa_location")
        if best:
            pdf = best.get("url_for_pdf") or best.get("url")
            return pdf
    except Exception:
        pass
    return None


# ============================================================
# PDF DOWNLOAD
# ============================================================

def download_pdf(url, doi):
    """Download a PDF to the pdfs/ folder."""
    filename = safe_filename(doi) + ".pdf"
    filepath = PDF_DIR / filename

    if filepath.exists():
        return True  # Already downloaded

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (THESIS Research Bot; mailto:ikukash@sharjah.ac.ae)"
        }
        resp = requests.get(url, timeout=60, headers=headers, stream=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            # Accept PDF or octet-stream
            if "pdf" in content_type or "octet-stream" in content_type or url.endswith(".pdf"):
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                # Verify it's actually a PDF
                with open(filepath, "rb") as f:
                    header = f.read(5)
                if header == b"%PDF-":
                    return True
                else:
                    filepath.unlink()  # Not a real PDF
                    return False
        return False
    except Exception as e:
        print(f"  [ERROR] Download failed for {doi}: {e}")
        return False


# ============================================================
# SNOWBALL — CITATION CHAIN FOLLOWING
# ============================================================

def get_cited_by(openalex_id, max_results=50):
    """Get papers that cite this work."""
    url = (
        f"{OPENALEX_API}/works?"
        f"filter=cites:{openalex_id.split('/')[-1]}"
        f"&per_page={min(max_results, 50)}&page=1"
        f"&mailto={MAILTO}"
        f"&select=id,doi,title,authorships,publication_year,"
        f"primary_location,cited_by_count,abstract_inverted_index,"
        f"open_access,referenced_works,cited_by_api_url,type"
    )
    papers = []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        for work in resp.json().get("results", [])[:max_results]:
            paper = parse_openalex_work(work)
            if paper:
                papers.append(paper)
    except Exception as e:
        print(f"  [ERROR] cited-by lookup failed: {e}")
    return papers


def get_references(referenced_work_ids, max_results=50):
    """Fetch full metadata for referenced works."""
    papers = []
    # OpenAlex IDs are like "https://openalex.org/W1234567"
    ids = [wid.split("/")[-1] for wid in referenced_work_ids[:max_results]]
    if not ids:
        return papers

    # Batch fetch (OpenAlex supports pipe-separated filter)
    batch_size = 25
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        filter_str = "|".join(batch)
        url = (
            f"{OPENALEX_API}/works?"
            f"filter=openalex:{filter_str}"
            f"&per_page=50&page=1"
            f"&mailto={MAILTO}"
            f"&select=id,doi,title,authorships,publication_year,"
            f"primary_location,cited_by_count,abstract_inverted_index,"
            f"open_access,referenced_works,cited_by_api_url,type"
        )
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            for work in resp.json().get("results", []):
                paper = parse_openalex_work(work)
                if paper:
                    papers.append(paper)
        except Exception as e:
            print(f"  [ERROR] reference lookup failed: {e}")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return papers


# ============================================================
# CSV I/O
# ============================================================

CSV_FIELDS = [
    "doi", "title", "authors", "year", "journal", "abstract",
    "cited_by_count", "is_oa", "oa_url", "pdf_url",
    "pdf_downloaded", "source_query", "region_relevant"
]


def save_metadata(papers):
    """Save/append papers to CSV."""
    file_exists = METADATA_CSV.exists()

    with open(METADATA_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for p in papers:
            p["region_relevant"] = is_region_relevant(
                f"{p.get('title','')} {p.get('abstract','')} {p.get('journal','')}"
            )
            writer.writerow(p)


def load_existing_metadata():
    """Load existing CSV if it exists."""
    if not METADATA_CSV.exists():
        return []
    papers = []
    with open(METADATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            papers.append(row)
    return papers


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_search(queries, max_per_query=100):
    """Run seed queries and collect papers."""
    seen = load_seen_dois()
    all_papers = []

    for i, query in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Searching: '{query}'")
        papers = search_openalex(query, max_results=max_per_query)
        new_count = 0

        for p in papers:
            if p["doi"] not in seen:
                p["source_query"] = query
                all_papers.append(p)
                seen.add(p["doi"])
                new_count += 1

        print(f"  Found {len(papers)} results, {new_count} new")

    save_seen_dois(seen)
    return all_papers


def run_unpaywall(papers):
    """Check Unpaywall for free PDFs."""
    print(f"\nChecking Unpaywall for {len(papers)} papers...")
    found = 0

    for i, p in enumerate(papers):
        if p.get("oa_url"):
            p["pdf_url"] = p["oa_url"]
            found += 1
            continue

        pdf_url = check_unpaywall(p["doi"])
        if pdf_url:
            p["pdf_url"] = pdf_url
            found += 1

        if (i + 1) % 50 == 0:
            print(f"  Checked {i+1}/{len(papers)} ({found} PDFs found)")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"  Total PDFs available: {found}/{len(papers)}")
    return papers


def run_downloads(papers):
    """Download available PDFs."""
    to_download = [p for p in papers if p.get("pdf_url") and not p.get("pdf_downloaded")]
    print(f"\nDownloading {len(to_download)} PDFs...")
    success = 0

    for i, p in enumerate(to_download):
        ok = download_pdf(p["pdf_url"], p["doi"])
        if ok:
            p["pdf_downloaded"] = True
            success += 1

        if (i + 1) % 20 == 0:
            print(f"  Downloaded {i+1}/{len(to_download)} ({success} successful)")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"  Successfully downloaded: {success}/{len(to_download)}")
    return papers


def run_snowball(papers, max_cited_by=20, max_refs=20):
    """Follow citation chains for high-impact papers."""
    seen = load_seen_dois()
    snowball_papers = []

    # Only snowball highly-cited or highly-relevant papers
    candidates = [
        p for p in papers
        if is_region_relevant(f"{p.get('title','')} {p.get('abstract','')}")
        and int(p.get("cited_by_count", 0)) > 10
    ]
    candidates.sort(key=lambda p: int(p.get("cited_by_count", 0)), reverse=True)
    candidates = candidates[:30]  # Top 30 most-cited relevant papers

    print(f"\nSnowballing from {len(candidates)} high-impact papers...")

    for i, p in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {p['title'][:60]}... (cited {p.get('cited_by_count', 0)}x)")

        # Papers that cite this one
        if p.get("openalex_id"):
            cited_by = get_cited_by(p["openalex_id"], max_results=max_cited_by)
            for cb in cited_by:
                if cb["doi"] not in seen and is_region_relevant(
                    f"{cb.get('title','')} {cb.get('abstract','')}"
                ):
                    cb["source_query"] = f"snowball:cited_by:{p['doi']}"
                    snowball_papers.append(cb)
                    seen.add(cb["doi"])
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # Papers this one references
        refs = p.get("referenced_works", [])
        if refs:
            ref_papers = get_references(refs, max_results=max_refs)
            for rp in ref_papers:
                if rp["doi"] not in seen and is_region_relevant(
                    f"{rp.get('title','')} {rp.get('abstract','')}"
                ):
                    rp["source_query"] = f"snowball:refs:{p['doi']}"
                    snowball_papers.append(rp)
                    seen.add(rp["doi"])
            time.sleep(DELAY_BETWEEN_REQUESTS)

    save_seen_dois(seen)
    print(f"  Snowball found {len(snowball_papers)} new relevant papers")
    return snowball_papers


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Scrape papers for RAG system")
    parser.add_argument("--download", action="store_true", help="Download available PDFs")
    parser.add_argument("--snowball", action="store_true", help="Follow citation chains")
    parser.add_argument("--max-per-query", type=int, default=100, help="Max results per query")
    args = parser.parse_args()

    # Create directories
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Search
    papers = run_search(SEED_QUERIES, max_per_query=args.max_per_query)
    print(f"\n{'='*60}")
    print(f"Total unique papers from search: {len(papers)}")

    # Step 2: Snowball (optional)
    if args.snowball:
        snowball = run_snowball(papers)
        papers.extend(snowball)
        print(f"Total after snowball: {len(papers)}")

    # Step 3: Check Unpaywall for PDFs
    papers = run_unpaywall(papers)

    # Step 4: Save metadata
    save_metadata(papers)
    print(f"\nMetadata saved to: {METADATA_CSV}")

    # Step 5: Download PDFs (optional)
    if args.download:
        papers = run_downloads(papers)

    # Summary
    total = len(papers)
    with_pdf = sum(1 for p in papers if p.get("pdf_url"))
    downloaded = sum(1 for p in papers if p.get("pdf_downloaded"))
    relevant = sum(1 for p in papers if is_region_relevant(
        f"{p.get('title','')} {p.get('abstract','')}"
    ))

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total papers found:     {total}")
    print(f"Region-relevant:        {relevant}")
    print(f"Open-access PDF found:  {with_pdf}")
    print(f"PDFs downloaded:        {downloaded}")
    print(f"{'='*60}")
    print(f"\nMetadata: {METADATA_CSV}")
    print(f"PDFs:     {PDF_DIR}")
    if not args.download:
        print(f"\nRun with --download to fetch PDFs")
    if not args.snowball:
        print(f"Run with --snowball to follow citation chains")


if __name__ == "__main__":
    main()
