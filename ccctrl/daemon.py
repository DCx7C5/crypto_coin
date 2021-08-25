from asyncio import create_subprocess_shell, Event
from asyncio.subprocess import PIPE
from os import getuid
from pwd import getpwuid
from os import path

from typing import Optional, Union

_pw = getpwuid(getuid())
USER = _pw.pw_name
HOME = _pw.pw_dir


class WalletDaemon:
    __slots__ = ('daemon_path', 'binary_name', 'client_path', 'name', 'cfg_file',
                 'options', 'data_dir', 'auto_config', '_data_dir_unlocked')

    def __init__(self, daemon_path: str, data_dir: str = None, auto_config: bool = False, **options: str):
        if not path.exists(daemon_path):
            raise Exception('Binary file not found!')

        self.daemon_path: str = daemon_path
        self.binary_name: str = daemon_path.split('/')[-1]
        self.client_path: str = f'{daemon_path}'
        self.name: str = daemon_path.split('/')[-1][:-1]
        self.data_dir: Optional[str] = data_dir or f'{HOME}/.{self.name}'
        self.auto_config: bool = auto_config
        self._data_dir_unlocked: Event = Event()

        self.options: list[str] = []

        if data_dir:
            self.options.append(data_dir)

        for k, v in options.items():
            self.options.append(f'{k}={v}')

        # check for running daemon
        if path.exists(f'{self.data_dir}/.lock'):
            self._data_dir_unlocked.set()

        cfg_path = f'{self.data_dir}/{self.name}.conf'
        self.cfg_file = None

        if path.exists(cfg_path):
            with open(cfg_path, 'rb') as cfg_file:
                self.cfg_file = cfg_file.read().decode('utf-8').splitlines()

    @classmethod
    async def create(cls,
                     binary_path: str,
                     data_dir: str = None,
                     auto_config: bool = False,
                     **options: str
                     ) -> "WalletDaemon":

        return cls(
            binary_path=binary_path,
            data_dir=data_dir,
            auto_config=auto_config,
            **options)

    async def start_daemon(self):
        await self._data_dir_unlocked.wait()
        await self._exec_binary(['--daemon'])

    async def stop_daemon(self):
        await self._exec_binary(['stop'])

    async def dmn_help(self) -> str:
        return await self._exec_binary(['--help'])

    async def _exec_binary(self, opts: list[str], as_list=False) -> Union[list[str], str]:
        cmd = f'{self.client_path if "stop" in opts else self.daemon_path} {" ".join(opts)}'
        proc = await create_subprocess_shell(cmd=cmd, stdout=PIPE, stderr=PIPE)
        out, err = await proc.communicate()
        if err:
            raise Exception(f'{err.decode("utf-8")}')
        if as_list:
            return out.decode('utf-8').splitlines()
        return out.decode('utf-8')

    def __repr__(self):
        return f'<BinaryDaemon {self.daemon_path}>'
