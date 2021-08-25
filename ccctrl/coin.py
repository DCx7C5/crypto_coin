from asyncio import get_event_loop

from .client import RpcClient
from .daemon import WalletDaemon

class CoinController:

    __slots__ = ('_name', '_host', '_port', '_rpc_user',
                 '_rpc_password', '_daemon_ctrl', 'loop', '_params',
                 'daemon', 'client', '_config_file', '_data_dir',
                 '_max_threads', )

    def __init__(self,
                 name: str,
                 host: str,
                 port: int,
                 rpc_user: str,
                 rpc_password: str,
                 daemon_ctrl: bool = False,
                 loop=None):
        self._name = name
        self._host = host
        self._port = port
        self._rpc_user = rpc_user
        self._rpc_password = rpc_password
        self._daemon_ctrl = daemon_ctrl
        self._params = None
        self.loop = loop or get_event_loop()

        self._ext_init()

    def _ext_init(self):
        self._params = ['-listen=0', '--listenonion=0']
        self._params.append('')

    @property
    def rpc_url(self):
        return f'{self._host}:{self._port}'

    @property
    def daemon_params(self):
        params = []
        params.append('--daemon ')
        params.append()
        return f'--daemon ' \
               f'{"-conf="}'

    @classmethod
    async def create_coin_ctrl(cls, name: str = None, host: str = None, port: int = None,
                               rpc_user: str = None, rpc_password: str = None,
                               daemon=False, loop=None) -> "CoinController":
        return cls(name, host, port, rpc_user, rpc_password, daemon, loop)

    async def start(self):
        if self._daemon_ctrl:
            await self.start_daemon()
        await self.start_rpc_client()

    async def start_daemon(self):
        self.daemon = await WalletDaemon.create(binary_path=)

    async def start_rpc_client(self):
        self.client = await RpcClient.create()

    def __repr__(self):
        return f'<CoinController {self._name} url={self.rpc_url} daemon={self._daemon} client={}'
