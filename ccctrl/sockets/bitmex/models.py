

class _RawReprMixin:
    def __repr__(self):
        value = ' '.join('%s=%r' % (attr, getattr(self, attr)) for attr in self.__slots__)
        return '<%s %s>' % (self.__class__.__name__, value)


class BitmexInstrumentUpdateEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_instrument_update` event.

    """
    __slots__ = ('symbol', 'data')

    def __init__(self, data):
        self.symbol = data['symbol']
        self.data = data


class BitmexOrderBookUpdateEvent(_RawReprMixin):
    __slots__ = ('symbol', 'data', 'cached_table')
