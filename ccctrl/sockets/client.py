# -*- coding: utf-8 -*-

import asyncio
import logging
import sys
import signal
import traceback
from typing import Optional, Union, Coroutine

from aiohttp import ClientError
from discord import ConnectionClosed, GatewayNotFound
from discord.backoff import ExponentialBackoff

from core.http import HttpClient
from core.errors import HTTPException
from core.errors import ReconnectWebSocket
from sockets.base_state import ConnectionState
from sockets.binance.gateway import WebSocket

log = logging.getLogger(__name__)


def _cancel_tasks(loop):
    try:
        task_retriever = asyncio.Task.all_tasks
    except AttributeError:
        # future proofing for 3.9 I guess
        task_retriever = asyncio.all_tasks

    tasks = {t for t in task_retriever(loop=loop) if not t.done()}

    if not tasks:
        return

    log.info('Cleaning up after %d tasks.', len(tasks))
    for task in tasks:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
    log.info('All tasks finished cancelling.')

    for task in tasks:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'Unhandled exception during Client.run shutdown.',
                'exception': task.exception(),
                'task': task
            })


def _cleanup_loop(loop):
    try:
        _cancel_tasks(loop)
        if sys.version_info >= (3, 6):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        log.info('Closing the event loop.')
        loop.close()


class _ClientEventTask(asyncio.Task):
    def __init__(self, original_coro, event_name, coro, *, loop):
        super().__init__(coro, loop=loop)
        self.__event_name = event_name
        self.__original_coro = original_coro

    def __repr__(self):
        info = [
            ('state', self._state.lower()),
            ('event', self.__event_name),
            ('coro', repr(self.__original_coro)),
        ]
        if self._exception is not None:
            info.append(('exception', repr(self._exception)))
        return '<ClientEventTask {}>'.format(' '.join('%s=%s' % t for t in info))


class _BaseClient:
    r"""Represents a client connection that connects to Websockets.
    This class is used to interact with the Bitmex WebSocket and API.

    A number of options can be passed to the :class:`Client`.

    Parameters
    -----------
    max_candles: Optional[:class:`int`]
        The maximum number of messages to store in the internal message cache.
        This defaults to ``1000``. Passing in ``None`` disables the message cache.

    loop: Optional[:class:`asyncio.AbstractEventLoop`]
        The :class:`asyncio.AbstractEventLoop` to use for asynchronous operations.
        Defaults to ``None``, in which case the default event loop is used via
        :func:`asyncio.get_event_loop()`.

    assume_unsync_clock: :class:`bool`
        Whether to assume the system clock is unsynced. This applies to the ratelimit handling
        code. If this is set to ``True``, the default, then the library uses the time to reset
        a rate limit bucket given by Discord. If this is ``False`` then your system clock is
        used to calculate how long to sleep for. If this is set to ``False`` it is recommended to
        sync your system clock to Google's NTP server.

    Attributes
    -----------
    ws
        The websocket gateway the client is currently connected to. Could be ``None``.
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop that the client uses for HTTP requests and websocket operations.

    """
    def __init__(self, loop=None, **options):
        self.ws = None
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop() if loop is None else loop
        self._listeners = {}

        connector = options.pop('connector', None)
        proxy = options.pop('proxy', None)
        proxy_auth = options.pop('proxy_auth', None)
        unsync_clock = options.pop('assume_unsync_clock', True)
        self.http = None

        self._handlers = {
            'ready': self._handle_ready,
        }

        self._hooks = {
            'before_identify': self._call_before_identify_hook,
        }

        self.connection: ConnectionState = self._get_state(**options)
        self._closed = False
        self._ready = asyncio.Event()
        self.connection._get_websocket = self._get_websocket
        self.connection._get_client = lambda: self

    # internals

    def _get_websocket(self, market=None, *, shard_id=None):
        return self.ws

    def _get_state(self, **options):
        return ConnectionState(dispatch=self.dispatch, handlers=self._handlers,
                               hooks=self._hooks, syncer=self._syncer, http=self.http, loop=self.loop, **options)

    async def _syncer(self, guilds):
        await self.ws.request_sync(guilds)

    def _handle_ready(self):
        self._ready.set()

    @property
    def latency(self):
        """:class:`float`: Measures latency between a HEARTBEAT and a HEARTBEAT_ACK in seconds.
        This could be referred to as the Discord WebSocket protocol latency.
        """

        ws = self.ws
        return float('nan') if not ws else ws.latency

    def is_ws_ratelimited(self):
        """:class:`bool`: Whether the websocket is currently rate limited.
        This can be useful to know when deciding whether you should query members
        using HTTP or via the gateway.
        .. versionadded:: 1.6
        """
        ws = self.ws
        if ws:
            return ws.is_ratelimited()
        return False

    async def connect(self, *, reconnect=True, **options):
        """|coro|
        Creates a websocket connection and lets the websocket listen
        to messages from the Exchanges. This is a loop that runs the entire
        event system and miscellaneous aspects of the library. Control
        is not resumed until the WebSocket connection is terminated.
        Parameters
        -----------
        reconnect: :class:`bool`
            If we should attempt reconnecting, either due to internet
            failure or a specific failure on Discord's part. Certain
            disconnects that lead to bad state will not be handled (such as
            invalid sharding payloads or bad tokens).

        headers: :class:`Optional[dict]`

        Raises
        -------
        :exc:`.GatewayNotFound`
            If the gateway to connect to Discord is not found. Usually if this
            is thrown then there is a Discord API outage.
        :exc:`.ConnectionClosed`
            The websocket connection has been terminated.
        """

        if self.http is None:
            self.http = await HttpClient.create_client(loop=self.loop, **options)

        backoff = ExponentialBackoff()
        ws_params = {
            'initial': True,
        }
        while not self.is_closed():
            try:
                coro: Coroutine = WebSocket.from_client(self, **ws_params)
                self.ws = await asyncio.wait_for(coro, timeout=30.0)
                ws_params['initial'] = False

                while True:
                    await self.ws.poll_event()
            except ReconnectWebSocket as e:
                log.info('Got a request to %s the websocket.', e.op)
                self.dispatch('disconnect')
                ws_params.update(topic=11)
                continue
            except (OSError,
                    HTTPException,
                    GatewayNotFound,
                    ConnectionClosed,
                    ClientError,
                    asyncio.TimeoutError) as exc:

                self.dispatch('disconnect')
                if not reconnect:
                    await self.close()
                    if isinstance(exc, ConnectionClosed) and exc.code == 1000:
                        # clean close, don't re-raise this
                        return
                    raise

                if self.is_closed():
                    return

                # If we get connection reset by peer then try to RESUME
                if isinstance(exc, OSError) and exc.errno in (54, 10054):
                    ws_params.update(initial=False, topic=self.ws.session_id)
                    continue

                # We should only get this when an unhandled close code happens,
                # such as a clean disconnect (1000) or a bad state (bad token, no sharding, etc)
                # sometimes, discord sends us 1000 for unknown reasons so we should reconnect
                # regardless and rely on is_closed instead
                if isinstance(exc, ConnectionClosed):
                    if exc.code != 1000:
                        await self.close()
                        raise

                retry = backoff.delay()
                log.exception("Attempting a reconnect in %.2fs", retry)
                await asyncio.sleep(retry)
                # Always try to RESUME the connection
                # If the connection is not RESUME-able then the gateway will invalidate the session.
                # This is apparently what the official Discord client does.

    async def close(self):
        """|coro|
        Closes the connection to Discord.
        """
        if self._closed:
            return

        await self.http.close()
        self._closed = True

        if self.ws is not None and self.ws.open:
            await self.ws.close(code=1000)

        self._ready.clear()

    def is_ready(self):
        """:class:`bool`: Specifies if the client's internal cache is ready for use."""
        return self._ready.is_set()

    async def _run_event(self, coro, event_name, *args, **kwargs):
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                await self.on_error(event_name, *args, **kwargs)
            except asyncio.CancelledError:
                pass

    def _schedule_event(self, coro, event_name, *args, **kwargs):
        wrapped = self._run_event(coro, event_name, *args, **kwargs)
        # Schedules the task
        return _ClientEventTask(original_coro=coro, event_name=event_name, coro=wrapped, loop=self.loop)

    def dispatch(self, event, *args, **kwargs):
        log.debug('Dispatching event %s', event)
        method = 'on_' + event

        listeners = self._listeners.get(event)
        if listeners:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as exc:
                    future.set_exception(exc)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            self._schedule_event(coro, method, *args, **kwargs)

    def is_closed(self):
        """:class:`bool`: Indicates if the websocket connection is closed."""
        return self._closed

    async def _call_before_identify_hook(self, shard_id, *, initial=False):
        # This hook is an internal hook that actually calls the public one.
        # It allows the library to have its own hook without stepping on the
        # toes of those who need to override their own hook.
        await self.before_identify_hook(shard_id, initial=initial)

    async def before_identify_hook(self, shard_id, *, initial=False):
        """|coro|

        A hook that is called before IDENTIFYing a session. This is useful
        if you wish to have more control over the synchronization of multiple
        IDENTIFYing clients.

        The default implementation sleeps for 5 seconds.

        .. versionadded:: 1.4

        Parameters
        ------------
        shard_id: :class:`int`
            The shard ID that requested being IDENTIFY'd
        initial: :class:`bool`
            Whether this IDENTIFY is the first initial IDENTIFY.
        """

        if not initial:
            await asyncio.sleep(5.0)

    async def on_error(self, event_method, *args, **kwargs):
        """|coro|

        The default error handler provided by the client.

        By default this prints to :data:`sys.stderr` however it could be
        overridden to have a different implementation.
        Check :func:`~discord.on_error` for more details.
        """
        print('Ignoring exception in {}'.format(event_method), file=sys.stderr)
        traceback.print_exc()

    async def start(self, *args, **kwargs):
        """|coro|

        A shorthand coroutine for :meth:`login` + :meth:`connect`.

        Raises
        -------
        TypeError
            An unexpected keyword argument was received.
        """
        reconnect = kwargs.pop('reconnect', True)

        if kwargs:
            raise TypeError(f"unexpected keyword argument(s) {list(kwargs.keys())}")

        await self.connect(reconnect=reconnect)

    def run(self, *args, **kwargs):
        """A blocking call that abstracts away the event loop
        initialisation from you.

        If you want more control over the event loop then this
        function should not be used. Use :meth:`start` coroutine
        or :meth:`connect` + :meth:`login`.

        Roughly Equivalent to: ::

            try:
                loop.run_until_complete(start(*args, **kwargs))
            except KeyboardInterrupt:
                loop.run_until_complete(logout())
                # cancel all tasks lingering
            finally:
                loop.close()

        .. warning::

            This function must be the last function to call due to the fact that it
            is blocking. That means that registration of events or anything being
            called after this function call will not execute until it returns.
        """
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass

        async def runner():
            try:
                await self.start(*args, **kwargs)
            finally:
                if not self.is_closed():
                    await self.close()

        def stop_loop_on_completion(f):
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log.info('Received signal to terminate bot and event loop.')
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            log.info('Cleaning up tasks.')
            _cleanup_loop(loop)

        if not future.cancelled():
            try:
                return future.result()
            except KeyboardInterrupt:
                # I am unsure why this gets raised here but suppress it anyway
                return None

    async def wait_until_ready(self):
        """|coro|

        Waits until the client's internal cache is all ready.
        """
        await self._ready.wait()

    def wait_for(self, event, *, check=None, timeout: Optional[Union[int, float]] = None):
        """|coro|

        Waits for a WebSocket event to be dispatched.

        This could be used to wait for a user to reply to a message,
        or to react to a message, or to edit a message in a self-contained
        way.

        The ``timeout`` parameter is passed onto :func:`asyncio.wait_for`. By default,
        it does not timeout. Note that this does propagate the
        :exc:`asyncio.TimeoutError` for you in case of timeout and is provided for
        ease of use.

        In case the event returns multiple arguments, a :class:`tuple` containing those
        arguments is returned instead. Please check the
        :ref:`documentation <discord-api-events>` for a list of events and their
        parameters.

        This function returns the **first event that meets the requirements**.

        Examples
        ---------

        Waiting for a user reply: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$greet'):
                    channel = message.channel
                    await channel.send('Say hello!')

                    def check(m):
                        return m.content == 'hello' and m.channel == channel

                    msg = await client.wait_for('message', check=check)
                    await channel.send('Hello {.author}!'.format(msg))

        Waiting for a thumbs up reaction from the message author: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$thumb'):
                    channel = message.channel
                    await channel.send('Send me that \N{THUMBS UP SIGN} reaction, mate')

                    def check(reaction, user):
                        return user == message.author and str(reaction.emoji) == '\N{THUMBS UP SIGN}'

                    try:
                        reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
                    except asyncio.TimeoutError:
                        await channel.send('\N{THUMBS DOWN SIGN}')
                    else:
                        await channel.send('\N{THUMBS UP SIGN}')

        Parameters
        ------------
        event: :class:`str`
            The event name, similar to the :ref:`event reference <discord-api-events>`,
            but without the ``on_`` prefix, to wait for.
        check: Optional[Callable[..., :class:`bool`]]
            A predicate to check what to wait for. The arguments must meet the
            parameters of the event being waited for.
        timeout: Optional[:class:`float`]
            The number of seconds to wait before timing out and raising
            :exc:`asyncio.TimeoutError`.

        Raises
        -------
        asyncio.TimeoutError
            If a timeout is provided and it was reached.

        Returns
        --------
        Any
            Returns no arguments, a single argument, or a :class:`tuple` of multiple
            arguments that mirrors the parameters passed in the
            :ref:`event reference <discord-api-events>`.
        """

        future = self.loop.create_future()
        if check is None:
            def _check(*args):
                return True
            check = _check

        ev = event.lower()
        try:
            listeners = self._listeners[ev]
        except KeyError:
            listeners = []
            self._listeners[ev] = listeners

        listeners.append((future, check))
        return asyncio.wait_for(future, timeout)

    # event registration

    def event(self, coro):
        """A decorator that registers an event to listen to.

        You can find more info about the events on the :ref:`documentation below <discord-api-events>`.

        The events must be a :ref:`coroutine <coroutine>`, if not, :exc:`TypeError` is raised.

        Example
        ---------

        .. code-block:: python3

            @client.event
            async def on_ready():
                print('Ready!')

        Raises
        --------
        TypeError
            The coroutine passed is not actually a coroutine.
        """

        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('event registered must be a coroutine function')

        setattr(self, coro.__name__, coro)
        log.debug(f'{ coro.__name__} has successfully been registered as an event')
        return coro

    async def on_market(self, market):
        pass


