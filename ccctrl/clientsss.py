

from asyncio.tasks import sleep
from enum import Enum
from subprocess import run
from logging import getLogger
from aiohttp import ClientSession as ClientHttpSession
from bitcoinrpc import BitcoinRPC
from bitcoinrpc.bitcoin_rpc import RPCError


from secrets import randbelow, choice
from string import ascii_letters, digits
from typing import (Optional, Union, List, Dict, Iterable, Tuple)
from asyncio import (get_event_loop, create_subprocess_shell, subprocess)

from multidict import CIMultiDict

log = getLogger(__name__)


__all_commands__ = (
    'stop',
    'move',
    'getnetworkinfo',
    'getnettotals',
    'getconnectioncount',
    'getnetworkhashps',
    'getmininginfo',
    'getpeerinfo',
    'getchaintips',
    'getchaintxstats',
    'validateaddress',
    'getwalletinfo',
    'getblockchaininfo',
    'getnewaddress',
    'getaccount',
    'getaccountaddress',
    'getaddressesbyaccount',
    'getbalance',
    'getblockcount',
    'gettransaction',
    'sendfrom',
    'sendmany',
    'sendtoaddress',
    'getblock',
    'getblockhash',
    'listaccounts',
    'listtransactions',
    'rescanblockchain',
    'listreceivedbyaddress',
    '-getinfo'
)


class TransactionType(Enum):
    INT_FROM = 0
    INT_TO = 1
    EXT_FROM = 2
    EXT_TO = 3


class RewindingBlocks(RPCError):
    pass


class LoadingBlockIndex(RPCError):
    pass


class NotStoppableError(Exception):
    pass



async def is_address_type(addr: "Address", client: "WalletClient"):
    return await client.validate_address(addr)


async def exec_subprocess(cmd):
    proc = await create_subprocess_shell(
        cmd=cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return await proc.communicate()


class Address:
    __slots__ = ('address', 'client')

    def __repr__(self):
        return self.address

    def __len__(self):
        return len(self.address)

    def __eq__(self, address):
        if isinstance(address, Address):
            return self.address == str(address)
        raise TypeError(f'Must be :Address type')

    @classmethod
    async def convert(cls, ctx: ExtendedContext, argument) -> "Address":
        if await cls.is_address_format(argument):
            cli = ctx.coin_client or ctx.command.coin_client or ctx.command.parent.coin_client

        return cls()

    @classmethod
    async def from_wallet(cls, addr) -> "Address":
        cls.address = addr
        return cls()

    @staticmethod
    async def is_address_format(arg: Union[str, "Address"]):
        return arg.isalnum() and arg.startswith('N') and len(arg) == 34

    @classmethod
    async def from_string(cls, addr, cli=None) -> "Address":
        cls.address, cls.client = addr, cli
        return cls()


class Account:
    __slots__ = ('account', 'client', 'balance', 'user')
    __cache__ = set()

    def is_cached(self) -> bool:
        return self.account in Account.__cache__


class Tx:
    __slots__ = ('from_acc', 'to_acc',
                 'from_addr', 'to_addr',
                 'from_user', 'to_user',
                 'amount', 'send_func', 'client')

    @classmethod
    async def create_tx(cls,
                        client: "RpcClient",
                        **data) -> "Tx":
        cls.client = client
        cls.from_user, cls.to_user = data.get('from_user'), data.get('to_user')
        cls.from_acc, cls.to_acc = data['from_acc'], data['to_acc']
        cls.from_addr, cls.to_addr = data['from_addr'], data['to_addr']
        cls.to_addr = data['to_addr']
        cls.send_func = data['send_func']
        return cls()


class RpcClient:

    def __init__(self, name: str, symbol: str, binary: str,
                 host: str = '127.0.0.1', port: int = 8332,
                 loop=None, bot=None):
        self.rpc = None
        self.http = None
        self._binary = binary
        self.coin_name = name
        self.symbol = symbol
        self.loop = loop or get_event_loop()
        self.host, self.port = host, port
        self._confl = [host, port]
        self._confp = None
        self._bot = bot

    async def start_daemon_async(self,
                                 u: Optional[str] = None,
                                 pw: Optional[str] = None,
                                 daemon: bool = True,
                                 rpc_threads: int = 12):
        self._confl, self._confp = [self.host, self.port], None
        _user = u or f'{self.symbol.lower()}_user_{randbelow(1000)}'
        _pass = pw or f"{''.join(choice(ascii_letters + digits) for _ in range(64))}"

        _confp = f'-rpcuser={_user} ' \
                 f'-rpcpassword={_pass} ' \
                 f'-rpcallowip={self._confl[0]} ' \
                 f'-rpcport={self._confl[1]} ' \
                 f"-listen=0 " \
                 f'-logips=1 '

        log.debug(f"{_user, _pass, _confp}")
        cmd = f"{self._binary} " \
              f"{'--daemon' if daemon else ''} " \
              f"-rpcthreads={rpc_threads} " \
              f"-datadir={root_dir}/.wallets/{self.symbol} " + _confp

        stdout, stderr = await exec_subprocess(cmd)

        if (stderr != b'') and ('lock on data' in stderr.decode('utf-8')):
            await self.kill_daemon_async()
            await sleep(15)
            await self.start_daemon_async()
        elif stderr != b'':
            log.error("Unknown RPC Error")
            raise Exception(f"Unknown RPC Error: {stderr.decode('utf-8')}")
        self._confl.append(_user), self._confl.append(_pass)
        self._confp = _confp
        return True

    async def stop_daemon_async(self):
        stdout, stderr = await exec_subprocess(f"{self._binary[:-1]}-cli {self._confp} stop")
        if stderr != b'':
            emsg = "Couldn't stop coin daemon!"
            if self._bot:
                self._bot.reload_extension(f'cogs.wallet')
            else:
                raise NotStoppableError(emsg)
            log.error(emsg)
        log.info('Stopped Wallet daemon.')

    async def kill_daemon_async(self):
        stdout, stderr = await exec_subprocess(f'killall {self._binary}')
        if stderr != b'':
            log.error("Couldn't stop coin daemon!")
            if self._bot:
                self._bot.reload_extension(f'cogs.wallet')
            else:
                raise NotStoppableError("Couldn't stop coin daemon!")
        log.info('Killed Wallet daemon.')

    def stop_daemon(self):
        run([f"{self._binary[:-1]}-cli", f"{self._confp}", "stop"])

    async def rpc_call(self, *args, **kwargs):
        try:
            return await self.rpc.acall(*args, **kwargs)
        except RPCError as e:
            error_handler(e)

    async def connect_daemon(self, rpc_user=None, rpc_password=None):
        if rpc_user is not None:
            self._confl.append(rpc_user)
        if rpc_password is not None:
            self._confl.append(rpc_password)
        self.http = ClientSession()
        print(*self._confl)
        self.rpc = BitcoinRPC(*self._confl)

    async def stop(self):
        return await self.rpc_call('stop', [])

    async def move(self, from_account: str, to_account: str, amount: Union[str, int]) -> bool:
        return await self.rpc_call('move', [from_account, to_account, amount])

    async def get_info(self) -> dict:
        return await self.rpc_call('-getinfo', [])

    async def get_network_info(self) -> dict:
        return await self.rpc_call('getnetworkinfo', [])

    async def get_difficulty(self) -> float:
        return await self.rpc_call('getdifficulty', [])

    async def get_net_totals(self) -> dict:
        return await self.rpc_call('getnettotals', [])

    async def get_connection_count(self) -> int:
        return await self.rpc_call('getconnectioncount', [])

    async def get_network_hash_ps(self) -> int:
        return await self.rpc_call('getnetworkhashps', [])

    async def get_mining_info(self) -> int:
        return await self.rpc_call('getmininginfo', [])

    async def get_peer_info(self) -> dict:
        return await self.rpc_call('getpeerinfo', [])

    async def get_chain_tips(self) -> dict:
        return await self.rpc_call('getchaintips', [])

    async def get_chain_tx_stats(self) -> dict:
        return await self.rpc_call('getchaintxstats', [])

    async def validate_address(self, address: Union[str, Address]) -> bool:
        resp = await self.rpc_call('validateaddress', [address])
        return resp.get('isvalid', False)

    async def get_wallet_info(self) -> dict:
        return await self.rpc_call('getwalletinfo', [])

    async def get_blockchain_info(self) -> dict:
        return await self.rpc_call('getblockchaininfo', [])

    async def get_new_address(self, account_name: str) -> str:
        return await self.rpc_call('getnewaddress', [account_name])

    async def get_account(self, address: str) -> str:
        return await self.rpc_call('getaccount', [address])

    async def get_account_address(self, account_name: str) -> str:
        return await self.rpc_call('getaccountaddress', [account_name])

    async def get_addresses_by_account(self, account_name: str) -> list:
        return await self.rpc_call('getaddressesbyaccount', [account_name])

    async def get_balance(self, account_name: Optional[str] = None) -> float:
        return await self.rpc_call('getbalance', [account_name] if account_name else [])

    async def get_block_count(self) -> int:
        return await self.rpc_call('getblockcount', [])

    async def get_transaction(self, tx_id: str) -> dict:
        return await self.rpc_call('gettransaction', [tx_id])

    async def send_from(self, from_account: str, to_address: str, amount: Union[float, int]) -> str:
        return await self.rpc_call('sendfrom', [from_account, to_address, amount])

    async def send_many(self, from_account: str, addresses: list, amount: Union[float, int]) -> list:
        tx_amount = {addr: amount for addr in addresses}
        return await self.rpc_call('sendmany', [from_account, tx_amount])

    async def send_to_address(self, to_address: str, amount: Union[float, int]) -> list:
        return await self.rpc_call('sendtoaddress', [to_address, amount])

    async def get_block(self, hash_or_height: str) -> dict:
        return await self.rpc_call('getblock', [hash_or_height])

    async def get_block_hash(self, height: int) -> str:
        return await self.rpc_call('getblockhash', [height])

    async def list_accounts(self) -> dict:
        return await self.rpc_call('listaccounts', [])

    async def list_transactions(self, account_name: str = None) -> List[dict]:
        params = [] if not account_name else [account_name]
        return await self.rpc_call('listtransactions', params)

    async def list_received_by_address(self) -> List[dict]:
        return await self.rpc_call('listreceivedbyaddress', [])

    # Decorator for extended wallet functions

    async def list_received_by_address_only(self, address: str) -> List[dict]:
        return [a for a in await self.list_received_by_address() if a['address'] == address]

    async def address_was_used(self, addr: str) -> bool:

        def same_address(ad):
            return (ad['address'] == addr) and (ad['amount'] > 0)

        resp = await self.list_received_by_address_only(addr)
        for addr_dict in resp:
            same = same_address(addr_dict)
            if same: return True
        return False


class BinaryClient:

    def __init__(self):
        pass
