import decorators
import re

_LINK_OPEN = '[['
_LINK_CLOSE = ']]'
_SKIP_PREFIXES = frozenset(('File:', 'Image:', 'Wikipedia:', 'WP:', 'HELP:', 'Portal:', 'Talk:', 'User:', 'User talk:', 'Template:', 'Template talk:', 'Help:', 'Category:', 'Special:', 'MediaWiki:', 'Module:', 'Draft:'))
_REF_RE = re.compile(r'<ref>\b[^>/]*>.*?</ref\s*>', re.IGNORECASE | re.DOTALL)
_SELF_CLOSING_REF_RE = re.compile(r'<ref\b[^>]*/\s*>', re.IGNORECASE)

def strip_refs(text):
    text = _REF_RE.sub('', text)
    text = _SELF_CLOSING_REF_RE.sub('', text)
    return text

def strip_templates(text):
    result = []
    i = 0
    depth = 0
    n = len(text)

    while i < n:
        if text.startswith('{{', i):
            depth += 1
            i += 2
        elif text.startswith('}}', i):
            if depth > 0:
                depth -= 1
            i += 2
        else:
            if depth == 0:
                result.append(text[i])
            i += 1

    return ''.join(result)


def extract_data(text):
    if not text:
        return [], []
    
    text = strip_refs(text)
    text = strip_templates(text)
    
    links = []
    categories = []
    i = 0
    text_len = len(text)
    
    while i < text_len:
        start = text.find(_LINK_OPEN, i)
        if start == -1:
            break
        
        end = text.find(_LINK_CLOSE, start+2)
        if end == -1:
            break
        
        inner = text[start+2 : end]
        
        if inner.startswith('Category:'):
            cat = inner[9:].split('|', 1)[0].strip()
            if cat:
                categories.append(cat)
        elif not inner or inner.startswith('#'):
            pass
        else:
            colon = inner.find(':')
            if colon != -1:
                prefix = inner[:colon+1].capitalize()
                if prefix in _SKIP_PREFIXES:
                    i = end + 2
                    continue
            else:
                target = inner.split('|', 1)[0].split('#', 1)[0].strip()
                if target:
                    links.append(target)
        i = end + 2
    return links, categories

@decorators.graph_builder
@decorators.community_metadata
@decorators.category_statistics
@decorators.article_statistics
@decorators.title_collector
def process_page(page, state):
    state["pages_processed"] += 1

    links = page.get("links") or []
    state["link_counts"] += len(links)

    categories = page.get("categories") or []

    state["category_counts"] += (len(categories))

    return state