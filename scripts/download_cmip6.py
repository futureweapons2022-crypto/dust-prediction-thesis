"""
Download CMIP6 Dust Optical Depth (od550dust) from ESGF
========================================================
Variable: od550dust (Dust Aerosol Optical Depth at 550nm)
Models: GISS-E2-1-G, GISS-E2-1-H, MIROC-ES2L, MIROC6, MRI-ESM2-0
Experiments: historical, ssp245, ssp585
Frequency: monthly
Output: THESIS/data/cmip6/

Strategy:
1. Query ESGF search API for each model+experiment combo
2. Get file download URLs (HTTP)
3. Download .nc files with resume support
4. Organize by model/experiment folders
"""

import requests
import os
import sys
import time
import logging
from datetime import datetime

# --- Configuration ---
OUTPUT_DIR = r"C:\Users\LENOVO\Desktop\THESIS\data\cmip6"
LOG_FILE = os.path.join(OUTPUT_DIR, "download_log.txt")

ESGF_SEARCH = "https://esgf-node.llnl.gov/esg-search/search"

MODELS = [
    "GISS-E2-1-G",
    "GISS-E2-1-H",
    "MIROC-ES2L",
    "MIROC6",
    "MRI-ESM2-0",
]

EXPERIMENTS = ["historical", "ssp245", "ssp585"]
VARIABLE = "od550dust"
FREQUENCY = "mon"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger()


def search_datasets(model, experiment):
    """Search ESGF for datasets matching model+experiment+variable."""
    params = {
        "project": "CMIP6",
        "variable_id": VARIABLE,
        "source_id": model,
        "experiment_id": experiment,
        "frequency": FREQUENCY,
        "type": "Dataset",
        "format": "application/solr+json",
        "limit": 50,
        "latest": "true",
        "distrib": "true",
    }
    try:
        r = requests.get(ESGF_SEARCH, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["response"]["docs"]
    except Exception as e:
        log.error("Search failed for %s/%s: %s", model, experiment, e)
        return []


def get_file_urls(dataset_id):
    """Get HTTP download URLs for files in a dataset."""
    params = {
        "type": "File",
        "dataset_id": dataset_id,
        "format": "application/solr+json",
        "limit": 100,
    }
    try:
        r = requests.get(ESGF_SEARCH, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        urls = []
        for doc in data["response"]["docs"]:
            # Get HTTP URL from url field
            for url_str in doc.get("url", []):
                if "HTTPServer" in url_str or "http" in url_str.lower():
                    # Format: "url|mime|service"
                    parts = url_str.split("|")
                    if len(parts) >= 1:
                        url = parts[0]
                        if url.endswith(".nc"):
                            urls.append({
                                "url": url,
                                "filename": doc.get("title", os.path.basename(url)),
                                "size": doc.get("size", 0),
                            })
        return urls
    except Exception as e:
        log.error("File search failed for %s: %s", dataset_id, e)
        return []


def download_file(url, filepath, expected_size=0):
    """Download a file with resume support."""
    # Check if already downloaded
    if os.path.exists(filepath):
        local_size = os.path.getsize(filepath)
        if expected_size > 0 and local_size >= expected_size:
            log.info("  SKIP (already complete): %s", os.path.basename(filepath))
            return True
        elif expected_size == 0 and local_size > 0:
            log.info("  SKIP (exists, %d MB): %s", local_size // (1024*1024), os.path.basename(filepath))
            return True

    # Download with progress
    try:
        headers = {}
        mode = "wb"
        downloaded = 0

        # Resume partial download
        if os.path.exists(filepath):
            downloaded = os.path.getsize(filepath)
            headers["Range"] = "bytes=%d-" % downloaded
            mode = "ab"
            log.info("  Resuming from %d MB", downloaded // (1024*1024))

        r = requests.get(url, headers=headers, stream=True, timeout=120)

        if r.status_code == 416:  # Range not satisfiable = already complete
            log.info("  SKIP (complete): %s", os.path.basename(filepath))
            return True

        r.raise_for_status()

        total = int(r.headers.get("content-length", 0)) + downloaded
        total_mb = total / (1024 * 1024) if total > 0 else 0

        with open(filepath, mode) as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    sys.stdout.write("\r  %.1f%% of %.1f MB" % (pct, total_mb))
                    sys.stdout.flush()

        print()  # newline after progress
        log.info("  DONE: %s (%.1f MB)", os.path.basename(filepath), downloaded / (1024*1024))
        return True

    except Exception as e:
        log.error("  FAIL: %s — %s", os.path.basename(filepath), e)
        return False


def main():
    log.info("=" * 60)
    log.info("CMIP6 od550dust Download — Started %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("Models: %s", ", ".join(MODELS))
    log.info("Experiments: %s", ", ".join(EXPERIMENTS))
    log.info("Output: %s", OUTPUT_DIR)
    log.info("=" * 60)

    total_files = 0
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    for model in MODELS:
        for experiment in EXPERIMENTS:
            log.info("")
            log.info("[%s / %s] Searching ESGF...", model, experiment)

            # Create output folder
            folder = os.path.join(OUTPUT_DIR, model, experiment)
            os.makedirs(folder, exist_ok=True)

            # Search for datasets
            datasets = search_datasets(model, experiment)
            if not datasets:
                log.warning("  No datasets found!")
                continue

            log.info("  Found %d datasets", len(datasets))

            # Use first dataset (latest version)
            # Sort by version to get latest
            datasets.sort(key=lambda d: d.get("version", ""), reverse=True)

            files_downloaded = 0
            for ds in datasets[:1]:  # Take only latest version
                dataset_id = ds.get("id", "")
                version = ds.get("version", "unknown")
                log.info("  Dataset: %s (v%s)", ds.get("instance_id", dataset_id)[:80], version)

                # Get file URLs
                files = get_file_urls(dataset_id)
                if not files:
                    log.warning("  No files found for dataset!")
                    # Try alternate: search with instance_id
                    instance_id = ds.get("instance_id", "")
                    if instance_id:
                        files = get_file_urls(instance_id)

                if not files:
                    log.warning("  Still no files — skipping dataset")
                    continue

                log.info("  %d files to download", len(files))
                total_files += len(files)

                for f in files:
                    filepath = os.path.join(folder, f["filename"])
                    log.info("  Downloading: %s", f["filename"])
                    ok = download_file(f["url"], filepath, f.get("size", 0))
                    if ok:
                        if "SKIP" not in open(LOG_FILE, encoding="utf-8").read().split("\n")[-3]:
                            total_downloaded += 1
                        else:
                            total_skipped += 1
                        files_downloaded += 1
                    else:
                        total_failed += 1

                    # Small delay between files to be polite to ESGF
                    time.sleep(1)

            log.info("  [%s/%s] Done — %d files", model, experiment, files_downloaded)

    log.info("")
    log.info("=" * 60)
    log.info("FINISHED at %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("Total files: %d | Downloaded: %d | Skipped: %d | Failed: %d",
             total_files, total_downloaded, total_skipped, total_failed)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
