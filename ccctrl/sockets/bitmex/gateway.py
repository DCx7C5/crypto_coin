import orjson
from logging import getLogger

from aiohttp import WSMessage

from ..base_gateway import _BaseWebSocket
from ..rate_limiter import GatewayRatelimiter

log = getLogger(__name__)


class WebSocket(_BaseWebSocket):
    """Implements a WebSocket for Bitmex gateway.

    Attributes
    -----------

    """
    EXCHANGE = 'bitmex'
    BASE_URL = 'wss://www.bitmex.com/realtimemd?heartbeat=true'

    MESSAGE = 0
    SUBSCRIBE = 1
    UNSUBSCRIBE = 2

    def __init__(self, socket, *, loop):

        super().__init__(socket, loop=loop)
        self._rate_limiter = GatewayRatelimiter()
        self.log = getLogger(__name__)

    async def subscribe(self, market):
        payload = [
            self.MESSAGE,
            None,
            f'{market}',
            {'op': 'subscribe', 'args': [
                f":{market.upper()}"
            ]}
        ]
        await self.socket.send_json(payload)

    async def unsubscribe(self, shard_id, session_id, subscription_topic=None, market=None):
        payload = [
            self.MESSAGE,
            shard_id,
            session_id,
        ]
        if subscription_topic:
            payload.append(
                {'op': 'subscribe', 'args': f"{subscription_topic}"}
            )
        if subscription_topic and market:
            payload[-1]['args'] = payload[-1]['args'] + f":{market.UPPER}"

        await self.socket.send_json(payload)

    async def received_message(self, msg):

        msg = orjson.loads(msg)
        log.debug(orjson.dumps(msg))

        op = msg[0]
        payload = msg[3]

        if self._keep_alive:
            self._keep_alive.tick()

        if op == self.UNSUBSCRIBE:
            log.info('Shard ID %s topic unsubscribed %s.', self.shard_id, self.session_id)
            return

        elif op == self.MESSAGE and 'success' in payload:
            log.info('Shard ID %s topic subscribed %s.', self.shard_id, self.session_id)
            return

        table, action, data = payload['table'], payload['action'], payload['data']

        event = f'{table.upper()}_{action.upper()}'

        try:
            func = self.parsers[event]
        except KeyError:
            log.debug('Unknown event %s.', event)
        else:
            while data:
                func(data.pop())

        await self._remove_dispatched_listeners(event, data)

    async def connect(self) -> None:
        await self.subscribe('xbtusdt')
        await self.send_as_json([self.SUBSCRIBE, self.shard_id, self.session_id])
        msg: WSMessage = await self.socket.receive(timeout=self.max_heartbeat_timeout)
        self.dispatch('socket_raw_receive', msg)
        msg = orjson.loads(msg.data)
        self.log.debug(orjson.dumps(msg))
