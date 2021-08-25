from enum import Enum
from typing import Dict, Union, Callable

import orjson

from asyncio import AbstractEventLoop
from logging import getLogger

from aiohttp import ClientWebSocketResponse

from sockets.base_gateway import _BaseWebSocket

from sockets.rate_limiter import GatewayRatelimiter
from sockets.keep_alive import KeepAliveHandler


class EventType(Enum):
    DEPTH_UPDATE = 'depth'
    KLINE_UPDATE = 'kline'
    TICKER_UPDATE = 'ticker'
    TRADE_UPDATE = 'trade'


async def parse_event(stream):
    pass


class WebSocket(_BaseWebSocket):
    """Implements a WebSocket for Bitmex gateway.

    Attributes
    -----------

    """
    BASE_URL = 'wss://stream.binance.com:9443/stream?streams=bnbbtc@depth/bnbbtc@kline_1m'
    SUBSCRIBE = 'SUBSCRIBE'
    UNSUBSCRIBE = 'UNSUBSCRIBE'

    def __init__(self, socket: ClientWebSocketResponse, *, loop: AbstractEventLoop):
        super().__init__(socket, loop=loop)
        self.rate_limiter = GatewayRatelimiter(5, 1)
        self._keep_alive = KeepAliveHandler(ws=self)
        self.log = getLogger(__name__)
        self._counter = 0

    @property
    def counter(self):
        self._counter += 1
        return self._counter

    async def subscribe(self, market):
        market = market.lower()
        payload = {
            "method": self.SUBSCRIBE,
            "params": [
                f"{market}@trade",
                f"{market}@depth",
                f"{market}@kline_1h",
                f"{market}@ticker",
            ],
            "id": self._counter
        }
        await self.socket.send_json(payload)

    async def unsubscribe(self, session_id, subscription_topic=None, market=None):
        payload = {
            "method": self.SUBSCRIBE,
            "params": [
                f"{market}@{subscription_topic}",
            ],
            "id": self._counter
        }
        await self.socket.send_json(payload)

    async def received_message(self, msg) -> None:

        msg = orjson.loads(msg)
        self.log.debug(orjson.dumps(msg))

        if msg.get('results', False):
            print(msg['results'])
            return

        if self._keep_alive:
            self._keep_alive.tick()

        symbol, topic = msg['stream'].split('@')
        data: Dict[Union[int, float, str, bool]] = msg['data']

        topic: str = topic if 'kline' not in topic else topic[:-3]

        event: str = EventType(topic).name

        try:
            func: Callable = self.parsers[event]
        except KeyError:
            self.log.debug('Unknown event %s.', event)
        else:
            func(data)

        await self._remove_dispatched_listeners(event, data)
