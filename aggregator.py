from collections import defaultdict, Counter

GLOBAL_RESULTS = {
    "pages_processed": 0,
    "link_counts": 0,
    "category_counts": 0,
 
    "statistics": {
        "total_words": 0,
        "total_chars": 0,
        "largest_article": ("", 0),
        'density_sum': 0,
        'density_count': 0,
        'category_sum': 0,
        'category_count':0
    },
    
    "category_stats": Counter(), 
    
    "artifact_files": defaultdict(list)
}
