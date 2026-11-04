"""Edge guard: per-client token buckets in front of everything, failed auth counted separately.

The service runs one serverless replica on Railway, so in-process state is the whole picture.
The client key is Railway's edge-set X-Real-IP; without it (local runs) the socket peer is used.
"""
import math
import time
from collections import OrderedDict

from fastapi.responses import JSONResponse

REQUEST_RATE = 2.0  # sustained requests per second per client
REQUEST_BURST = 60
FAILURE_BURST = 10  # 401/403 answers a client may collect before it is locked out
FAILURE_REFILL_SECONDS = 30.0  # one failure forgiven per this many seconds
MAX_CLIENTS = 4096  # least recently seen clients are dropped beyond this

_now = time.monotonic


class _Buckets:
    __slots__ = ('at', 'failures', 'requests')

    def __init__(self, at):
        self.requests, self.failures, self.at = float(REQUEST_BURST), float(FAILURE_BURST), at

    def refill(self, at):
        elapsed = max(0.0, at - self.at)
        self.requests = min(REQUEST_BURST, self.requests + elapsed * REQUEST_RATE)
        self.failures = min(FAILURE_BURST, self.failures + elapsed / FAILURE_REFILL_SECONDS)
        self.at = at


class Limiter:
    def __init__(self):
        self.clients: OrderedDict[str, _Buckets] = OrderedDict()

    def _get(self, key, at):
        b = self.clients.get(key)
        if b is None:
            b = self.clients[key] = _Buckets(at)
            while len(self.clients) > MAX_CLIENTS:
                self.clients.popitem(last=False)
        else:
            self.clients.move_to_end(key)
            b.refill(at)
        return b

    def admit(self, key):
        """Return 0 to admit the request, else the seconds to wait."""
        b = self._get(key, _now())
        if b.failures < 1:
            return math.ceil((1 - b.failures) * FAILURE_REFILL_SECONDS)
        if b.requests < 1:
            return math.ceil((1 - b.requests) / REQUEST_RATE)
        b.requests -= 1
        return 0

    def failed(self, key):
        b = self._get(key, _now())
        b.failures = max(0.0, b.failures - 1)


def _client_key(scope):
    for name, value in scope.get('headers', []):
        if name == b'x-real-ip':
            return value.decode('latin-1')[:64]
    client = scope.get('client')
    return client[0] if client else 'unknown'


class EdgeGuard:
    def __init__(self, app):
        self.app, self.limiter = app, Limiter()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        key = _client_key(scope)
        wait = self.limiter.admit(key)
        if wait:
            response = JSONResponse({'detail': 'too many requests'}, 429, headers={'Retry-After': str(wait)})
            return await response(scope, receive, send)

        async def counted_send(message):
            if message['type'] == 'http.response.start' and message['status'] in (401, 403):
                self.limiter.failed(key)
            await send(message)

        await self.app(scope, receive, counted_send)
