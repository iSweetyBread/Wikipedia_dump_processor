import bz2
from lxml import etree
from concurrent.futures import ProcessPoolExecutor
from aggregator import GLOBAL_RESULTS
import os
from io import BytesIO
from text_utils import is_redirect, normalise_title, hash_title
from worker_state import init_worker
import numpy as np
from collections import Counter
from multiprocessing import shared_memory
from memory_throttle import WeightedSemaphore
import threading

NS_ARTICLE = '0'
PARSE_TAGS = ("{*}page", "{*}title", "{*}ns", "{*}id", "{*}revision", "{*}text",)
BZ2_EXPANSION_ESTIMATE = 4.5
DEFAULT_MAX_PENDING_MB = 2048

def parse_index(index_filepath):
    current_offset = None
    current_count = 0
    
    with bz2.open(index_filepath, "rt", encoding="utf-8") as f:
        for line in f:
            offset_str, page_id, title = line.rstrip("\n").split(":", 2)
            offset = int(offset_str)
            
            if offset != current_offset:
                if current_offset is not None:
                    yield (current_offset, current_count)
                current_offset = offset
                current_count = 0
                
            current_count += 1
            
    if current_offset is not None:
        yield (current_offset, current_count)
        
def build_stream_ranges(index_filepath, data_filepath):
    streams = list(parse_index(index_filepath))
    file_size = os.path.getsize(data_filepath)
    
    ranges = []
    for i, (start, count) in enumerate(streams):
        end = streams[i + 1][0] if i + 1 < len(streams) else file_size
        ranges.append((start, end, count))
        
    return ranges

def group_stream_ranges(stream_ranges, chunk_size=10_000):
    group = []
    group_count = 0
    
    for start, end, count in stream_ranges:
        group.append((start, end))
        group_count += count
        
        if group_count >= chunk_size:
            yield group
            group = []
            group_count = 0
            
    if group:
        yield group
        
def extract_pages(context):
    ns = title = page_id = text = None
    
    for _, element in context:
        tag = element.tag
        
        if tag.endswith("title"):
            title = element.text
        elif tag.endswith("ns"):
            ns = element.text
        elif tag.endswith("id"):
            parent = element.getparent()
            if parent is not None and parent.tag.endswith("page"):
                page_id = element.text
        elif tag.endswith("text"):
            text = element.text or ""
            
            if is_redirect(text):
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
                continue
        elif tag.endswith("page"):
            if ns == NS_ARTICLE:
                yield (title, page_id, text or "")        

            ns = title = page_id = text = None
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]

          
def iter_pages_from_stream(file_handle, start, end):
    file_handle.seek(start)
    raw = file_handle.read(end - start)
    
    xml_fragment = bz2.decompress(raw)
    wrapped = b"<mediawiki>" + xml_fragment + b"</mediawiki>"
    
    context = etree.iterparse(BytesIO(wrapped), events=("end",), tag=PARSE_TAGS, huge_tree=True, recover=True)
    
    yield from extract_pages(context)

def collect_known_title_hashes(index_filepath):
    hashes = set()
    with bz2.open(index_filepath, "rt", encoding="utf-8") as f:
        for line in f:
            _, _, title = line.rstrip("\n").split(":", 2)
            h = hash_title(normalise_title(title))
            hashes.add(h)
    return np.array(sorted(hashes), dtype=np.int64)

# \/ | LEGACY CODE FALLBACK | \/
def read(filepath):
    with bz2.open(filepath, "rb") as f:
        context = etree.iterparse(f, events=("end",), tag=PARSE_TAGS, huge_tree=True, recover=True)
        yield from extract_pages(context)
        
def chunker(page_stream, chunk_size=10_000):
    chunk = []
    
    for page in page_stream:
        chunk.append(page)
        
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
            
    if chunk:
        yield chunk
# /\ | LEGACY CODE FALLBACK | /\
    
def process_stream_group(chunk_id, data_filepath, stream_group, worker_func):
    pages = []
    with open(data_filepath, "rb") as f:
        for start, end in stream_group:
            pages.extend(iter_pages_from_stream(f, start, end))
            
    return worker_func(chunk_id, pages)

def global_reader(data_filepath, worker_func, index_filepath=None, max_workers=8, max_pending_mb=DEFAULT_MAX_PENDING_MB, chunk_size=10_000):
    use_multistream = index_filepath is not None and os.path.exists(index_filepath)
 
    title_hashes = collect_known_title_hashes(index_filepath)
 
    shm = shared_memory.SharedMemory(create=True, size=max(int(title_hashes.nbytes), 1))
    shm_view = np.ndarray(title_hashes.shape, dtype=np.int64, buffer=shm.buf)
    shm_view[:] = title_hashes
 
    throttle = WeightedSemaphore(max_pending_mb * 1024 * 1024)
 
    pending_category_stats = []
    results_lock = threading.Lock()
    all_done = threading.Event()
    pending = {"count": 0}
 
    def on_complete(future, weight):
        throttle.release(weight)
        try:
            result = future.result()
        except Exception as e:
            print(f"Error handling worker result: {e}")
            result = None
 
        with results_lock:
            if result is not None:
                handle_worker_result(result)
                pending_category_stats.append(result.get("category_stats") or {})
            pending["count"] -= 1
            if pending["count"] == 0:
                all_done.set()
 
    try:
        with ProcessPoolExecutor(max_workers=max_workers, initializer=init_worker, initargs=(shm.name, int(title_hashes.shape[0])),) as exec:
            if use_multistream:
                stream_ranges = build_stream_ranges(index_filepath, data_filepath)
                items = enumerate(group_stream_ranges(stream_ranges, chunk_size))
            else:
                items = enumerate(chunker(read(data_filepath), chunk_size))
 
            for chunk_id, item in items:
                if use_multistream:
                    compressed_bytes = sum(end - start for start, end in item)
                    weight = max(int(compressed_bytes * BZ2_EXPANSION_ESTIMATE), 1)
                else:
                    weight = max(sum(len(text.encode("utf-8")) for _t, _i, text in item), 1)
 
                throttle.acquire(weight)
 
                with results_lock:
                    pending["count"] += 1
 
                try:
                    if use_multistream:
                        future = exec.submit(process_stream_group, chunk_id, data_filepath, item, worker_func)
                    else:
                        future = exec.submit(worker_func, chunk_id, item)
                except Exception:
                    throttle.release(weight)
                    with results_lock:
                        pending["count"] -= 1
                        if pending["count"] == 0:
                            all_done.set()
                    raise
                
                future.add_done_callback(lambda f, w=weight: on_complete(f, w))
 
            with results_lock:
                if pending["count"] == 0:
                    all_done.set()
 
            all_done.wait()
    finally:
        shm.close()
        try:
            shm.unlink()
        except FileNotFoundError:
            pass
 
    merge_category_stats(pending_category_stats)

def handle_worker_result(result):
    GLOBAL_RESULTS["pages_processed"] += result["pages_processed"]
    GLOBAL_RESULTS["link_counts"] += result["link_counts"]
    GLOBAL_RESULTS["category_counts"] += result["category_counts"]

    for (artifact_name, path) in result["artifact_files"].items():
        GLOBAL_RESULTS["artifact_files"][artifact_name].append(path)

    worker_stats = result["statistics"]
    
    global_stats = GLOBAL_RESULTS["statistics"]
    global_stats["total_words"] += worker_stats.get("total_words", 0)
    global_stats["total_chars"] += worker_stats.get("total_chars", 0)
    global_stats["density_count"] += worker_stats.get("density_count", 0)
    global_stats["density_sum"] += worker_stats.get("density_sum", 0)
    global_stats["category_count"] += worker_stats.get("category_count", 0)
    global_stats["category_sum"] += worker_stats.get("category_sum", 0)

    worker_largest = worker_stats.get("largest_article", ("", 0))

    if worker_largest[1] > global_stats["largest_article"][1]:
        global_stats["largest_article"] = (worker_largest)
        
def merge_category_stats(pending_category_stats):
    merged = Counter()
    for category_stats in pending_category_stats:
        merged.update(category_stats)
    GLOBAL_RESULTS["category_stats"] = merged