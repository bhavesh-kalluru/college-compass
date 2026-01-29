import time
import threading
from dataclasses import dataclass


@dataclass
class RateLimiter:
    """
    Simple token-bucket rate limiter (in-process).
    Helps avoid bursty UI retries hammering APIs.
    """
    capacity: int = 5
    refill_per_sec: float = 0.5  # 1 token every 2 seconds
    _tokens: float = 5.0
    _last: float = time.time()
    _lock: threading.Lock = threading.Lock()

    def allow(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
