import threading

class WeightedSemaphore: 
    def __init__(self, max_weight):
        if max_weight <= 0:
            raise ValueError("max_weight must be positive")
        self._max_weight = max_weight
        self._used = 0
        self._cond = threading.Condition()
 
    def acquire(self, weight):
        weight = min(weight, self._max_weight)
        with self._cond:
            while self._used + weight > self._max_weight:
                self._cond.wait()
            self._used += weight
 
    def release(self, weight):
        with self._cond:
            self._used -= weight
            self._cond.notify_all()
