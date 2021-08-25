from logging import getLogger
from itertools import count

from yarl import URL
import orjson

from typing import (
    Optional,
    Literal,
    Union,
    List,
    Any,
)

from core.http import HttpClient
from core.types import (
    WalletResponseType,
    ChainTipsDetail,
    ConnectionCount,
    ValidateAddress,
    BestBlockHash,
    NetworkHashps,
    ChainTxStats,
    BlockHeader,
    MempoolInfo,
    BlockCount,
    Difficulty,
    MiningInfo,
    BlockHash,
    ChainTips,
    NodeInfo,
    Block,
)


from core.errors import (
    rpc_error_lookup_table,
)

log = getLogger(__name__)


_req_id = count(1)

rpc_methods = {
    'help': str,
}


class RPCClient(HttpClient):

    def __init__(self, host: str, port: int, **kwargs: Any):
        super().__init__(**kwargs)
        self.url: URL = URL(f"http://{host}:{port}")

    async def request(
        self,
        method: str,
        params: List[Optional[Union[str, int, List[str]]]] = None,
        json_data: Any = None,
        repeats: int = 5,
        **kwargs: Any,
    ) -> WalletResponseType:

        if params is None:
            params = []

        json_data = orjson.dumps({
            'method': method,
            'params': params,
            'id': next(_req_id),
            'jsonrpc': "2.0",
        })

        for tries in range(repeats):
            try:
                async with self.session.request(url=self.url, method='POST', proxy=self.proxy, data=json_data) as resp:

                    resp_data: dict = await resp.json()
                    error: Optional[dict] = resp_data.get('error', None)

                    if not error and not self.verbose:
                        return resp_data['result']

                    errcode, errmsg = error['code'], error['message']

                    raise rpc_error_lookup_table[errcode](f'{errmsg}')

            except OSError as e:
                if tries < 4 and e.errno in (54, 10054):
                    continue
                raise

    # == GENERAL ==

    async def help(self) -> str:
        return await self.request('help')

    async def stop(self) -> None:
        return await self.request('stop')

    async def uptime(self):
        return await self.request('uptime')

    # == Blockchain ==

    async def get_best_blockhash(self) -> BestBlockHash:
        return BestBlockHash(value=await self.request(method='getbestblockhash'))

    async def get_block(self, blockhash: str, verbose: bool = False) -> Block:
        return Block(**await self.request(method='getblock', params=[blockhash, 2 if verbose else 1]))

    async def get_blockchain_info(self):
        return await self.request(method='getblockchaininfo')

    async def get_block_count(self) -> BlockCount:
        return BlockCount(value=await self.request(method='getblockcount'))

    async def get_block_hash(self, height: int) -> BlockHash:
        return BlockHash(value=await self.request(method='getblockhash', params=[height]))

    async def get_block_header(self, blockhash: str) -> BlockHeader:
        return BlockHeader(**await self.request(method='getblockheader', params=[blockhash]))

    async def get_chaintips(self) -> ChainTips:
        resp = await self.request(method='getchaintips')
        return [ChainTipsDetail(**c) for c in resp]

    async def get_chain_tx_stats(self, nblocks: int = None, blockhash: str = None) -> ChainTxStats:
        return ChainTxStats(**await self.request(method='getchaintxstats', params=[nblocks, blockhash]))

    async def get_difficulty(self) -> Difficulty:
        return Difficulty(value=await self.request(method='getdifficulty'))

    async def get_mempool_ancestors(self, txid: str, verbose: bool = True):
        return await self.request(method='getmempoolancestors', params=[txid, verbose])

    async def get_mempool_descendants(self, txid: str, verbose: bool = True):
        return await self.request(method='getmempooldescendants', params=[txid, verbose])

    async def get_mempool_entry(self, txid: str):
        return await self.request(method='getmempoolentry', params=[txid])

    async def get_mempool_info(self) -> MempoolInfo:
        return MempoolInfo(**await self.request(method='getmempoolinfo'))

    async def get_raw_mempool(self):
        return await self.request(method='getrawmempool')

    # == Mining ==

    async def get_mining_info(self) -> MiningInfo:
        return MiningInfo(**await self.request(method='getmininginfo'))

    async def get_networkhash_ps(self, nblocks: int = 120, height: int = 1) -> NetworkHashps:
        return NetworkHashps(value=await self.request(method='getrawmempool', params=[nblocks, height]))

    # == Network ==

    async def add_node(self, node: str, command: Literal['add', 'remove', 'onetry']) -> None:
        return await self.request(method='addnode', params=[node, command])

    async def clear_banned(self) -> None:
        """Clear all banned IPs."""
        return await self.request(method='clearbanned')

    async def get_added_nodeinfo(self, node: str) -> NodeInfo:
        """Returns information about the given added node, or all added nodes"""
        info = await self.request(method='getaddednodeinfo', params=[node])
        print(info)

    async def get_connection_count(self) -> ConnectionCount:
        return ConnectionCount(value=await self.request(method='getconnectioncount'))

    async def get_net_totals(self):
        return await self.request(method='getnettotals')

    async def get_network_info(self):
        return await self.request(method='getnetworkinfo')

    async def get_peer_info(self):
        return await self.request(method='getpeerinfo')

    async def list_banned(self):
        return await self.request(method='listbanned')

    async def ping(self) -> None:
        """Requests that a ping be sent to all other nodes, to measure ping time.
        Results provided in getpeerinfo, pingtime and pingwait fields are decimal seconds."""
        return await self.request(method='ping')

    # == Wallet ==

    async def validate_address(self, address: str) -> ValidateAddress:
        return ValidateAddress(**await self.request(method='validateaddress', params=[address]))

