from collections import defaultdict
from functools import wraps

from plugin_registry import register_artifact
from text_utils import normalise_title

@register_artifact("edges", "worker_{worker_id}_edges.tsv")
def graph_builder(func):
    @wraps(func)
    def wrapper(page, state):
        title = normalise_title(page.get('title') or '')
        links = page.get('links') or []
        known_titles = state.get('_known_titles') or frozenset()

        state.setdefault('edges', [])

        targets = {normalise_title(link) for link in links}
        
        for target in targets:
            if target and target != title and target in known_titles:
                state['edges'].append((title, target))

        return func(page, state)

    return wrapper


def article_statistics(func):
    @wraps(func)
    def wrapper(page, state):
        text = page.get('text') or ''
        links = page.get('links') or []
        categories = page.get('categories') or []
        
        word_count = len(text.split())
        char_count = len(text)
        
        state.setdefault('statistics', {
            'total_words': 0,
            'total_chars': 0,
            'largest_article': ('', 0),
            'density_sum': 0,
            'density_count': 0,
            'category_sum': 0,
            'category_count':0
        })
        
        stats = state['statistics']
        
        stats['total_words'] += word_count
        stats['total_chars'] += char_count
        
        if word_count > stats['largest_article'][1]:
            stats['largest_article'] = (page.get('title', ''), word_count)
            
        if word_count > 0:
            stats["density_sum"] += len(links)/word_count
            stats["density_count"] += 1
            
        if categories:
            stats["category_sum"] += len(categories)
            stats["category_count"] += 1
                    
        return func(page, state)
    
    return wrapper

def category_statistics(func):
    @wraps(func)
    def wrapper(page, state):
        categories = page.get('categories') or []

        if 'category_stats' not in state:
            state['category_stats'] = defaultdict(int)

        for category in categories:
            state['category_stats'][category] += 1

        return func(page, state)

    return wrapper

@register_artifact("community_metadata", "worker_{worker_id}_community.pkl")
def community_metadata(func):
    @wraps(func)
    def wrapper(page, state):
        title = normalise_title(page.get('title') or '')
        categories = page.get('categories') or []
        links = page.get('links') or []
        if not categories and not links:
            return func(page, state)

        state.setdefault('community_metadata', {})

        state['community_metadata'][title] = {
            'categories': categories,
            'degree': len(links)
        }

        return func(page, state)

    return wrapper

def title_collector(func):
    @wraps(func)
    def wrapper(page, state):
        state.setdefault("titles", [])
        
        state["titles"].append(page.get("title", ""))

        return func(page, state)

    return wrapper