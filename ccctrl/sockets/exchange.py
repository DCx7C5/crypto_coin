import os
from sockets.bitmex.gateway import WebSocket
from sockets.binance.gateway import BinanceWebSocket

cwd = __file__.replace('/exchange.py', '')

__all_as_strings__ = [p for p in os.listdir(cwd) if ('.' not in p) and ('_' not in p)]


class Exchange:
    __slots__ = ('name', 'socket_cls', 'base_url')

    def __init__(self, name: str):
        self.name = name
        if self.name == 'bitmex':
            self.socket_cls = WebSocket
            self.base_url: str = 'wss://www.bitmex.com/realtimemd?heartbeat=true'
        elif self.name == 'binance':
            self.socket_cls = BinanceWebSocket
            self.base_url: str = 'wss://stream.binance.com:9443'
