import threading
import time
import traceback
import concurrent.futures
from asyncio import run_coroutine_threadsafe

from logging import getLogger
from sys import _current_frames

from typing import Any


log = getLogger(__name__)


class KeepAliveHandler(threading.Thread):
    def __init__(self, *args, **kwargs: Any):
        ws = kwargs.get('ws', None)
        interval = kwargs.pop('interval', None)

        threading.Thread.__init__(self, *args, **kwargs)
        self.ws = ws
        self._main_thread_id = ws.thread_id
        self.interval = interval
        self.daemon = True
        self.msg = 'Keeping websocket alive with sequence %s.'
        self.block_msg = 'heartbeat blocked for more than %s seconds.'
        self.behind_msg = 'Can\'t keep up, websocket is %.1fs behind.'
        self._stop_ev = threading.Event()
        self._last_ack = time.perf_counter()
        self._last_send = time.perf_counter()
        self._last_recv = time.perf_counter()
        self.latency = float('inf')
        self.heartbeat_timeout = ws._max_heartbeat_timeout

    def run(self):
        while not self._stop_ev.wait(self.interval):
            if self._last_recv + self.heartbeat_timeout < time.perf_counter():
                log.warning("Shard ID %s has stopped responding to the gateway. Closing and restarting.")
                coro = self.ws.close(4000)
                f = run_coroutine_threadsafe(coro, loop=self.ws.loop)

                try:
                    f.result()
                except Exception:
                    log.exception('An error occurred while stopping the gateway. Ignoring.')
                finally:
                    self.stop()
                    return

            data = self.get_payload()
            log.debug(self.msg, data['d'])
            coro = self.ws.send_heartbeat(data)
            f = run_coroutine_threadsafe(coro, loop=self.ws.loop)
            try:
                # block until sending is complete
                total = 0
                while True:
                    try:
                        f.result(10)
                        break
                    except concurrent.futures.TimeoutError:
                        total += 10
                        try:
                            frame = _current_frames()[self._main_thread_id]
                        except KeyError:
                            msg = self.block_msg
                        else:
                            stack = traceback.format_stack(frame)
                            msg = '%s\nLoop thread traceback (most recent call last):\n%s' % (self.block_msg, ''.join(stack))
                        log.warning(msg, total)

            except Exception:
                self.stop()
            else:
                self._last_send = time.perf_counter()

    def get_payload(self):
        return {
            'op': self.ws.HEARTBEAT,
            'd': self.ws.sequence
        }

    def stop(self):
        self._stop_ev.set()

    def tick(self):
        self._last_recv = time.perf_counter()

    def ack(self):
        ack_time = time.perf_counter()
        self._last_ack = ack_time
        self.latency = ack_time - self._last_send
        if self.latency > 10:
            log.warning(self.behind_msg, self.latency)

