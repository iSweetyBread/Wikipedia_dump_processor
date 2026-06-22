import time
from reader_func import global_reader
from worker_func import core_worker
from aggregator import GLOBAL_RESULTS
from graph_analysis import analyze_graph
from file_manager import report_print, cleanup_worker_artifacts
import argparse

WIKI_DUMP = r'data\enwiki-20260601-pages-articles-multistream.xml.bz2'
WIKI_INDEX = r'data\enwiki-20260601-pages-articles-multistream-index.txt.bz2'
# WIKI_DUMP = r'data\enwiki_100k.xml.bz2'

def parse_args():
    parser = argparse.ArgumentParser(description="Wikipedia dump processor")

    parser.add_argument("-f", "--file", default=WIKI_DUMP, help="Path to Wikipedia dump file")
    parser.add_argument("-i", "--index", default=WIKI_INDEX, help="Path to Wikipedia dump index file")
    parser.add_argument("-c", "--chunk_size", type=int, default=10_000, help="Chunk size for processing")
    parser.add_argument("-m", "--max_pending_mb", type=int, default=2048, help="Approx. memory budget (MB) for chunks submitted but not yet processed")

    return parser.parse_args()

def finalize_results():
    stats = GLOBAL_RESULTS["statistics"]

    avg_density = (
        stats["density_sum"] / stats["density_count"]
        if stats["density_count"] else 0
    )

    avg_categories = (
        stats['category_sum'] / stats['category_count']
        if stats["category_count"] else 0
    )

    return {
        "pages_processed": GLOBAL_RESULTS["pages_processed"],
        "link_counts": GLOBAL_RESULTS["link_counts"],
        "category_counts": GLOBAL_RESULTS["category_counts"],
        "largest_article": stats["largest_article"],
        "total_words": stats["total_words"],
        "total_chars": stats["total_chars"],
        "average_link_density": avg_density,
        "average_categories": avg_categories,
        "unique_categories": len(GLOBAL_RESULTS["category_stats"]),
        "artifact_files": dict(GLOBAL_RESULTS["artifact_files"])
    }
    
def main():
    start_time = time.time()
    
    args = parse_args()

    print("Starting Wikipedia dump processing...")
    report_print(f"Input file: {args.file}")

    global_reader(data_filepath=args.file, worker_func=core_worker, index_filepath=args.index, max_workers=8, max_pending_mb=args.max_pending_mb, chunk_size = args.chunk_size)

    results = finalize_results()

    total_time_1 = time.time() - start_time

    report_print("\n===== PROCESSING RESULTS =====")
    report_print(f"Pages processed: {results['pages_processed']:,}")
    report_print(f"Links found: {results['link_counts']:,}")
    report_print(f"Categories found: {results['category_counts']:,}")
    report_print(f"Unique categories: {results['unique_categories']:,}")

    report_print("\nStatistics:")
    report_print(f"Total words: {results['total_words']:,}")
    report_print(f"Total chars: {results['total_chars']:,}")

    title, words = results["largest_article"]
    report_print(f"Largest article: '{title}' ({words:,} words)")

    report_print(f"Average link density: {results['average_link_density']:.4f}")

    report_print(f"Average categories/article: {results['average_categories']:.2f}")

    print("\nGenerated artifact files:")
    for artifact, files in results["artifact_files"].items():
        print(f"  {artifact}: {len(files)} files")

    report_print(f"\nTotal dump processing runtime: {total_time_1:.2f} seconds")
    
    graph_result = analyze_graph()

    report_print("\n===== BASIC GRAPH ANALYSIS RESULTS =====")

    report_print(f"Nodes: {graph_result['stats']['nodes']:,}")
    report_print(f"Edges: {graph_result['stats']['edges']:,}")
    report_print(f"Communities: {len(graph_result['communities']):,}")
    
    cleanup_worker_artifacts(results["artifact_files"])
    total_time_2 = time.time() - start_time
    report_print(f"\nTotal runtime: {total_time_2:.2f} seconds")

if __name__ == "__main__":
    main()