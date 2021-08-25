import json
import threading
from asyncio import AbstractEventLoop, TimeoutError, Future
from collections import namedtuple
from logging import Logger

import orjson
from aiohttp import ClientWebSocketResponse, WSMessage, WSMsgType
from typing import Optional, Callable, Union, List, Dict

from core.errors import ConnectionClosed
from core.errors import WebSocketClosure, ReconnectWebSocket
from .keep_alive import KeepAliveHandler
from .rate_limiter import GatewayRatelimiter


def to_json(obj):
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=True)


EventListener = namedtuple('EventListener', 'predicate event result future')


class EventType:
    close = 0
    reconnect = 1
    resume = 2
    identify = 3
    terminate = 4
    clean_close = 5


class _BaseWebSocket:
    BASE_URL: str = None

    MESSAGE: int = None
    SUBSCRIBE: int = None
    UNSUBSCRIBE: int = None

    def __init__(self, socket, *, loop):
        self.socket: ClientWebSocketResponse = socket
        self.loop: AbstractEventLoop = loop
        # an empty dispatcher to prevent crashes
        self.dispatch: Callable = lambda *args: None
        self.thread_id: int = threading.get_ident()
        self._keep_alive: Optional[KeepAliveHandler] = None
        self.parsers: Dict[str, Callable] = {}
        # generic event listeners
        self._dispatch_listeners: List[EventListener] = []
        self.max_heartbeat_timeout: Optional[Union[int, float]] = None
        # ws related stuff
        self.session_id: Optional[str] = None
        self._close_code: Optional[int] = None
        self.shard_id: Optional[str] = None
        self.rate_limiter: Optional[GatewayRatelimiter] = None
        self.log: Optional[Logger] = None

    @property
    def open(self) -> bool:
        return not self.socket.closed

    def wait_for(self, event, predicate, result=None) -> Future:
        """Waits for a EVENT that meets the predicate.
        Parameters
        -----------
        event: :class:`str`
            The event name in all upper case to wait for.
        predicate
            A function that takes a data parameter to check for event
            properties. The data parameter is the 'd' key in the JSON message.
        result
            A function that takes the same data parameter and executes to send
            the result to the future. If ``None``, returns the data.
        Returns
        --------
        asyncio.Future
            A future to wait for.
        """

        future = self.loop.create_future()
        entry = EventListener(event=event, predicate=predicate, result=result, future=future)
        self._dispatch_listeners.append(entry)
        return future

    def is_ratelimited(self) -> bool:
        return self.rate_limiter.is_ratelimited()

    async def subscribe(self, *args, **kwargs) -> None:
        pass

    async def unsubscribe(self, *args, **kwargs) -> None:
        pass

    def _can_handle_close(self) -> bool:
        code = self._close_code or self.socket.close_code
        return code not in (1000, 4004, 4010, 4011, 4012, 4013, 4014)

    async def poll_event(self) -> None:
        """Polls for a EVENT and handles the general gateway loop.
        Raises
        ------
        ConnectionClosed
            The websocket connection was terminated for unhandled reasons.
        """
        try:
            event: WSMessage = await self.socket.receive(timeout=self.max_heartbeat_timeout)
            if event.type is WSMsgType.TEXT:
                await self.received_message(event.data)
            elif event.type is WSMsgType.BINARY:
                await self.received_message(event.data)
            elif event.type is WSMsgType.PONG:
                await self.received_message(event.data)
            elif event.type is WSMsgType.ERROR:
                self.log.debug('Received %s', event)
                raise event.data
            elif event.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                self.log.debug('Received %s', event)
                raise WebSocketClosure
        except (TimeoutError, WebSocketClosure) as e:
            # Ensure the keep alive handler is closed
            if self._keep_alive:
                self._keep_alive.stop()
                self._keep_alive = None
            if isinstance(e, TimeoutError):
                self.log.info('Timed out receiving packet. Attempting a reconnect.')
                raise ReconnectWebSocket() from None

            code = self._close_code or self.socket.close_code
            if self._can_handle_close():
                self.log.info('Websocket closed with %s, attempting a reconnect.', code)
                raise ReconnectWebSocket() from None
            else:
                self.log.info('Websocket closed with %s, cannot reconnect.', code)
                raise ConnectionClosed(self.socket, code=code) from None

    async def send(self, data) -> None:
        await self.rate_limiter.block()
        self.dispatch('socket_raw_send', data)
        await self.socket.send_str(data)

    async def send_as_json(self, data) -> None:
        try:
            await self.send(to_json(data))
        except RuntimeError as exc:
            if not self._can_handle_close():
                raise ConnectionClosed(self.socket) from exc

    async def close(self, code=4000) -> None:
        if self._keep_alive:
            self._keep_alive.stop()
            self._keep_alive = None

        self._close_code = code
        await self.socket.close(code=code)

    async def received_message(self, msg) -> None:
        pass

    @classmethod
    async def from_client(cls, client, *, initial=False, topic=None):
        """Creates a main websocket for Discord from a :class:`Client`.
        This is for internal use only.
        """
        socket = await client.http.ws_connect(cls.BASE_URL)
        ws = cls(socket, loop=client.loop)
        # dynamically add attributes needed
        ws.connection = client.connection
        ws.parsers = client.connection.parsers
        ws.dispatch = client.dispatch
        ws.call_hooks = client.connection.call_hooks
        ws.initial_identify = initial
        ws.session_id = 0
        ws.max_heartbeat_timeout = client.connection.heartbeat_timeout

        ws.log.info(f'Created websocket connected to {cls.BASE_URL}')

        await ws.connect()
        return ws

    async def connect(self):
        msg: WSMessage = await self.socket.receive(timeout=self.max_heartbeat_timeout)
        self.dispatch('socket_raw_receive', msg)
        msg = orjson.loads(msg.data)
        self.log.debug(orjson.dumps(msg))

    async def _remove_dispatched_listeners(self, event, data):
        removed = []
        for index, entry in enumerate(self._dispatch_listeners):
            if entry.event != event:
                continue

            future = entry.future
            if future.cancelled():
                removed.append(index)
                continue

            try:
                valid = entry.predicate(data)
            except Exception as exc:
                future.set_exception(exc)
                removed.append(index)
            else:
                if valid:
                    if entry.result is None:
                        ret = data
                    else:
                        ret = entry.result(data)
                    future.set_result(ret)
                    removed.append(index)

        for index in reversed(removed):
            del self._dispatch_listeners[index]
