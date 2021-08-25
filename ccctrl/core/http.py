import asyncio
import json
from types import TracebackType
from logging import getLogger

from aiohttp import (
    BaseConnector,
    TCPConnector,
)

from typing import (
    Optional,
    Mapping,
    Type,
    Any,
)


from core.errors import (
    HTTPException,
    Forbidden,
    NotFound,
)

from aiohttp import (
    ClientResponse,
    ClientSession,
    BasicAuth,
)

from core.utils import ccctrl_user_agent

log = getLogger(__name__)


async def json_or_text(response):
    text = await response.text(encoding='utf-8')
    try:
        if response.headers['content-type'] == 'application/json':
            return json.loads(text)
    except KeyError:
        # Thanks Cloudflare
        pass

    return text


class HttpClient:

    __slots__ = ('auth', 'proxy', '_connector', 'loop',
                 'headers', 'session', '_unlocked', '_resp_cls',
                 '_repeats_on_error', 'verbose')

    def __init__(self, *,
                 auth_user: str = None,
                 auth_pass: str = None,
                 proxy_user: str = None,
                 proxy_pass: str = None,
                 loop: asyncio.AbstractEventLoop = None,
                 **kwargs: Any,
                 ) -> None:

        self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()

        self.auth: Optional[BasicAuth] = BasicAuth(
            login=auth_user,
            password=auth_pass,
            encoding='utf-8') if (auth_user and auth_pass) else None

        self.proxy: Optional[BasicAuth] = BasicAuth(
            login=proxy_user,
            password=proxy_pass,
            encoding='utf-8') if (proxy_user and proxy_pass) else None

        self.headers: dict = {
            'content-type': 'application/json',
        }
        self.headers.update(kwargs.get('headers', {}))

        max_conns: int = 100 if isinstance(self, HttpClient) else kwargs.get('max_connections', 30)

        self._resp_cls: Type[ClientResponse] = ClientResponse

        self._connector: BaseConnector = TCPConnector(
            loop=self.loop,
            limit=max_conns,
            ttl_dns_cache=60 * 60
        )

        self._repeats_on_error: int = 5

        self.session: Optional[ClientSession] = None

        self._unlocked = asyncio.Event()
        self._unlocked.set()

    @classmethod
    async def create_client(cls, *args, **kwargs: Any) -> "HttpClient":
        cli = cls(*args, **kwargs)
        cli.session = await cli.create_session()
        return cli

    async def create_session(self) -> ClientSession:

        return ClientSession(
            auth=self.auth,
            headers=self.headers,
            connector=self._connector,
            response_class=self._resp_cls
        )

    async def request(
            self,
            url: str,
            method: str = None,
            params: Mapping[str, str] = None,
            data: Any = None,
            **kwargs: Any
    ):

        if not method:
            method = 'GET'

        for tries in range(self._repeats_on_error):
            try:
                async with self.session.request(method, url, **kwargs) as resp:

                    log.info(f'{method} {url} with {data} has returned {resp.status}')

                    resp_data = await json_or_text(resp)

                    if 300 > resp.status >= 200:
                        log.debug(f'{method} {url} has received {resp_data}')
                        return resp, resp_data

                    if resp.status == 429:
                        # Checks for rate limits
                        if not resp.headers.get('Via'):
                            raise HTTPException(resp, resp_data)

                        retry_after = resp_data['retry_after'] / 1000.0
                        log.warning(f'We are being rate limited. Retrying in {retry_after:.2f} seconds.')

                        is_global = resp_data.get('global', False)
                        if is_global:
                            log.warning(f'Global rate limit has been hit. Retrying in {retry_after:.2f} seconds.')
                            self._unlocked.clear()

                        await asyncio.sleep(retry_after)
                        log.info('Done sleeping for the rate limit. Retrying...')

                        if is_global:
                            self._unlocked.set()
                            log.debug('Global rate limit is now over.')
                        continue

                    if resp.status in {500, 502}:
                        await asyncio.sleep(1 + tries * 2)
                        continue
                    if resp.status == 403:
                        raise Forbidden(resp, resp_data)
                    elif resp.status == 404:
                        raise NotFound(resp, resp_data)
                    else:
                        raise HTTPException(resp, resp_data)

            except OSError as e:
                # Connection reset by peer
                if tries < 4 and e.errno in (54, 10054):
                    continue
                raise

        raise HTTPException(resp, resp_data)

    async def recreate_session(self):
        self.session = await self.create_session()

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:

        await self.close()
        return None

    async def close(self) -> None:
        await self.session.close()

    async def ws_connect(self, url, *, compress=0):
        kwargs = {
            'proxy': self.proxy,
            'timeout': 30.0,
            'autoclose': False,
            'headers': {
                'User-Agent': ccctrl_user_agent
            },
            'compress': compress
        }
        if self.session is None:
            await self.create_session()

        return await self.session.ws_connect(url, **kwargs)
