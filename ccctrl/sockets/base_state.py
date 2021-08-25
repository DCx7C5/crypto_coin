import asyncio
import gc
import inspect
import logging
from asyncio import Task
from weakref import WeakValueDictionary
from collections import OrderedDict
from os import urandom


from typing import (
    Optional,
    Callable,
    Dict, Union
)

from core.http import HttpClient


class ChunkRequest:
    def __init__(self, guild_id, loop, resolver, *, cache=True):
        self.guild_id = guild_id
        self.resolver = resolver
        self.loop = loop
        self.cache = cache
        self.nonce = urandom(16).hex()
        self.buffer = []
        self.waiters = []

    def add_members(self, members):
        self.buffer.extend(members)
        if self.cache:
            guild = self.resolver(self.guild_id)
            if guild is None:
                return

            for member in members:
                existing = guild.get_member(member.id)
                if existing is None or existing.joined_at is None:
                    guild._add_member(member)

    async def wait(self):
        future = self.loop.create_future()
        self.waiters.append(future)
        try:
            return await future
        finally:
            self.waiters.remove(future)

    def get_future(self):
        future = self.loop.create_future()
        self.waiters.append(future)
        return future

    def done(self):
        for future in self.waiters:
            if not future.done():
                future.set_result(self.buffer)


log = logging.getLogger(__name__)


async def logging_coroutine(coroutine, *, info):
    try:
        await coroutine
    except Exception:
        log.exception(f'Exception occurred during {info}')


class ConnectionState:

    def __init__(self, *, dispatch, handlers, hooks, syncer, http, loop, **options):
        self.loop: asyncio.AbstractEventLoop = loop
        self.http: HttpClient = http

        self._by_market_symbol: Optional[Dict[str, ]] = None
        self._market_tables = None
        self._ticker_tables = None
        self._obook_tables = None
        self._trade_tables = None
        self._cline_tables = None

        self.dispatch: Callable = dispatch
        self.syncer = syncer
        self.handlers = handlers
        self.hooks = hooks
        self._ready_task: Optional[Task] = None
        self._ready_state: Optional[asyncio.Queue] = None

        self.heartbeat_timeout: Union[int, float] = options.get('heartbeat_timeout', 6)

        self.parsers = parsers = {}
        for attr, func in inspect.getmembers(self):
            if attr.startswith('parse_'):
                parsers[attr[6:].upper()] = func

        self.clear()

    def clear(self) -> None:
        """Resets ConnectionState to default values.
        """
        self._markets = WeakValueDictionary()

        # LRU of max size 128
        self._market_tables = OrderedDict()

        self._ticker_tables = {}
        self._obook_tables = {}
        self._trade_tables = {}
        self._cline_tables = {}

        # In cases of large deallocations the GC should be called explicitly
        # To free the memory more immediately, especially true when it comes
        # to reconnect loops which cause mass allocations and deallocations.
        gc.collect()

    def call_handlers(self, key, *args, **kwargs):
        try:
            func = self.handlers[key]
        except KeyError:
            pass
        else:
            func(*args, **kwargs)

    async def call_hooks(self, key, *args, **kwargs):
        try:
            coro = self.hooks[key]
        except KeyError:
            pass
        else:
            await coro(*args, **kwargs)

    async def _delay_ready(self):
        try:
            try:
                del self._ready_state
            except AttributeError:
                pass  # already been deleted somehow

        except asyncio.CancelledError:
            pass
        else:
            # dispatch the event
            self.call_handlers('ready')
            self.dispatch('ready')
        finally:
            self._ready_task = None

    @property
    def markets(self) -> list:
        return list(self._markets.values())

    def _get_market(self, symbol):
        return self._markets.get(symbol)

    def _add_market(self, market):
        self._markets[market.symbol] = market

    def _remove_market(self, market):
        self._markets.pop(market.symbol, None)

        del market
        # Much like clear(), if we have a massive deallocation
        # then it's better to explicitly call the GC
        # in this case if all tables of all symbols of an exchange get rm'd
        gc.collect()

    def parse_ready(self, data):
        if self._ready_task is not None:
            self._ready_task.cancel()

        self._ready_state = asyncio.Queue()
        self.clear()

        self.dispatch('connect')

        # Much like clear(), if we have a massive deallocation
        # then it's better to explicitly call the GC
        # Note that in the original ready parsing code this was done
        # implicitly via clear() but in the auto sharded client clearing
        # the cache would have the consequence of clearing data on other
        # shards as well.
        gc.collect()

        if self._ready_task is None:
            self._ready_task = asyncio.ensure_future(self._delay_ready(), loop=self.loop)

    def parse_resumed(self, data):
        self.dispatch('resumed')

    # Binance Stream Parsers

    def parse_kline_update(self, data):
        print('KLINE UPDATE', data)
        timestamp: int = data['E']

    def parse_depth_update(self, data):
        print('DEPTH UPDATE', data)

    def parse_ticker_update(self, data):
        print('TICKER UPDATE', data)

