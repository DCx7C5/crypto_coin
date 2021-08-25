from time import time_ns
from dataclassy import dataclass
from dataclassy.dataclass import DataClassMeta


def timefunc(f):
    def f_timer(*args, **kwargs):
        start = time_ns()
        result = f(*args, **kwargs)
        end = time_ns()
        print(f.__name__, 'took', end - start, 'ns time')
        return result
    return f_timer


class AsyncioMeta(DataClassMeta):
    async def __call__(cls, *args, **kwargs):
        return super(AsyncioMeta, cls).__call__(*args, **kwargs)


class SingleAttrDataClsMeta(DataClassMeta):
    async def __call__(cls, *args, **kwargs):
        return super(SingleAttrDataClsMeta, cls).__call__(*args, **kwargs).count


@dataclass(slots=True, frozen=True, eq=True, compare=True, unsafe_hash=False)
class ConnectionCountA:
    counter: int


@dataclass(slots=False, frozen=True, eq=True, compare=True, unsafe_hash=True)
class ConnectionCountB:
    counter: int


@dataclass(slots=True, frozen=True, eq=True, compare=True)
class ConnectionCountC:
    counter: int


@dataclass(slots=True, frozen=True, eq=True, compare=True, meta=AsyncioMeta, unsafe_hash=True)
class ConnectionCountD:
    counter: int


@dataclass(slots=False, frozen=True, eq=True, compare=True, meta=AsyncioMeta, unsafe_hash=True)
class ConnectionCountE:
    counter: int


@dataclass(slots=True, frozen=True, eq=True, compare=True, meta=AsyncioMeta, unsafe_hash=True)
class ConnectionCountF:
    counter: int




@timefunc
def a():
    for x in range(1000000):
        y = ConnectionCountA(x)
    return y


@timefunc
def b():
    for x in range(1000000):
        y = ConnectionCountB(x)


@timefunc
def c():
    for x in range(1000000):
        y = ConnectionCountC(x)
    return y


@timefunc
async def d():
    for x in range(1000000):
        y = await ConnectionCountD(x)
    return y


@timefunc
async def e():
    for x in range(1000000):
        y = await ConnectionCountE(x)
    return y


@timefunc
async def f():
    for x in range(1000000):
        y = await ConnectionCountF(x)
    return y

a()
b()
c()
await d()
await e()
await f()

