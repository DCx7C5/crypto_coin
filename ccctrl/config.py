from configparser import ConfigParser


class CoinConfig:

    __slots__ = ('listen', 'server')

    def __init__(self, **options):
        for k, v in options.items():
            self.__setattr__(k, v)
