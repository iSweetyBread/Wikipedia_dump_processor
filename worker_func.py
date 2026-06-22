import time
import os
from collections import defaultdict
from helpers_func import process_page, extract_data
from serializer import dump_registered_artifacts
import worker_state

OUTPUT_DIR = r'data/workers'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def dump_worker_data(worker_id, state):
    artifact_files = dump_registered_artifacts(worker_id, state, OUTPUT_DIR)

    return {
        "worker_id": worker_id,
        "pages_processed": state["pages_processed"],
        "link_counts": state["link_counts"],
        "category_counts": state["category_counts"],
        "statistics": state.get("statistics", {}),
        "category_stats": dict(state.get("category_stats", {})),
        "artifact_files": artifact_files,
    }

def core_worker(chunk_id, chunk):
    start_time = time.time()

    state = {
        "pages_processed": 0,
        "titles": [],
        "link_counts": 0,
        "category_counts": 0,
        "plugin_results": defaultdict(dict),
        "_known_titles": worker_state.KNOWN_TITLES
    }

    for title, page_id, text in chunk:
        text = text or ''
        page = {
            "title": title,
            "id": page_id,
            "text": text
        }
        links, categories = extract_data(text)
        page["links"] = links
        page["categories"] = categories
        try:
            state = process_page(page, state)
        except Exception as e:
            print(f"Error processing page {page.get('title')}: {e}")

    result = dump_worker_data(chunk_id, state)
    total_time = time.time() - start_time
    result['total_time'] = total_time

    print(f"[chunk {chunk_id}] {state['pages_processed']} pages in {total_time:.2f}s")

    return result