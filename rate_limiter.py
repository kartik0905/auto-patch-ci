import asyncio
import time

class TokenBucketRateLimiter:
    """
    An asyncio-compatible token bucket rate limiter.
    Strictly enforces a requests-per-minute (RPM) limit by generating a
    given number of tokens over time.
    """
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """
        Acquires a token from the bucket. Suspends the coroutine until a
        token becomes available if the bucket is empty.
        """
        async with self.lock:
            while True:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                # If no tokens are available, calculate wait time
                wait_time = (1 - self.tokens) / self.refill_rate
                await asyncio.sleep(wait_time)

    def _refill(self):
        """
        Calculates how many tokens should be added to the bucket based on
        the elapsed time since the last refill.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        if new_tokens > 0:
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

# Groq free tier limit is 30 RPM
# This means capacity is 30, and refill rate is 30 tokens / 60 seconds = 0.5 tokens/sec
groq_rate_limiter = TokenBucketRateLimiter(capacity=30, refill_rate=30/60)
