import hashlib

def normalise_title(title):
    if not title:
        return title
    
    title = title.split('#', 1)[0]
    title = title.strip().replace('_', ' ')
    
    if not title:
        return title
    
    return title[0].upper() + title[1:]

def is_redirect(text):
    return (text or '').lstrip().upper().startswith('#REDIRECT')

def hash_title(title):
    digest = hashlib.blake2b(title.encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(digest, 'little', signed=True)