import atexit
import numpy as np
from multiprocessing import shared_memory
from text_utils import hash_title

KNOWN_TITLES = frozenset()
_shm_handle = None

class SharedTitleSet:
    __slots__ = ("_shm", "_hashes")

    def __init__(self, shm_name, length):
        self._shm = shared_memory.SharedMemory(name=shm_name)
        self._hashes = np.ndarray((length,), dtype=np.int64, buffer=self._shm.buf)

    def __contains__(self, title):
        if not title:
            return False
        h = hash_title(title)
        idx = np.searchsorted(self._hashes, h)
        return idx < len(self._hashes) and self._hashes[idx] == h

    def close(self):
        self._shm.close()


def init_worker(shm_name, length):
    global KNOWN_TITLES, _shm_handle
    KNOWN_TITLES = SharedTitleSet(shm_name, length)
    _shm_handle = KNOWN_TITLES
    atexit.register(KNOWN_TITLES.close)