import time
from asyncio import sleep, Lock
from logging import getLogger

log = getLogger(__name__)


class GatewayRatelimiter:

    def __init__(self, count=40, per=60*60):
        self.max = count
        self.remaining = count
        self.window = 0.0
        self.per = per
        self.lock = Lock()

    def is_ratelimited(self):
        current = time.time()
        if current > self.window + self.per:
            return False
        return self.remaining == 0

    def get_delay(self):
        current = time.time()

        if current > self.window + self.per:
            self.remaining = self.max

        if self.remaining == self.max:
            self.window = current

        if self.remaining == 0:
            return self.per - (current - self.window)

        self.remaining -= 1
        if self.remaining == 0:
            self.window = current

        return 0.0

    async def block(self):
        async with self.lock:
            delta = self.get_delay()
            if delta:
                log.warning('WebSocket is ratelimited, waiting %.2f seconds', delta)
                await sleep(delta)
