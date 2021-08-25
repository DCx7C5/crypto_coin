import datetime
from dataclassy import dataclass

from numpy import (
    ndarray,
)



@dataclass(slots=True, frozen=True, repr=True, eq=True)
class Candle:
    o: float
    h: float
    l: float
    c: float
    v: float
    t: datetime.datetime


@dataclass(slots=True)
class OhlcvTable:

    __slots__ = ('o', 'h', 'l', 'c', 'v', 't')

    def __init__(self, **kwargs):
        self.o: ndarray = kwargs.get('o')
        self.h: ndarray = kwargs.get('h')
        self.l: ndarray = kwargs.get('l')
        self.c: ndarray = kwargs.get('c')
        self.v: ndarray = kwargs.get('v')
        self.t: ndarray = kwargs.get('t')

    async def from_table(self, table):
