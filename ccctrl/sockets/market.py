

class Market:

    __slots__ = ('_symbol_raw', '_symbol', '_exchange',)

    def __init__(self, symbol, exchange):
        self._symbol_raw: str = symbol
        self._exchange: str = exchange
