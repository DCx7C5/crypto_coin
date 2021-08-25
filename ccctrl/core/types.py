from enum import Enum
from dataclassy import dataclass
from typing_extensions import Literal
from yarl import URL

from typing import (
    TypeVar,
    Union,
    Dict,
    List,
    Any, TypedDict,
)


StrOrURL = Union[str, URL]

BlockHash = str
BestBlockHash = str
ConnectionCount = int
Difficulty = float
BlockCount = int


@dataclass(kwargs=True, slots=True)
class NetworkHashps:
    value: float

    def in_MHps(self):
        return self.value / 1024

    def in_GHps(self):
        return self.value / 1024 / 1024


@dataclass(kwargs=True, slots=True)
class _RawTransaction:
    txid: str
    hash: BlockHash
    version: int
    size: int
    vsize: int
    locktime: int
    vin: List[Dict[str, Any]]
    vout: List[Dict[str, Any]]
    hex: str
    blockhash: str
    confirmations: str
    time: int
    blocktime: int


RawTransaction = Union[str, _RawTransaction]


@dataclass(kwargs=True, slots=True)
class BlockHeader:
    hash: BlockHash
    confirmations: int
    height: BlockCount
    version: int
    versionHex: str
    merkleroot: str
    time: int
    mediantime: int
    nonce: int
    bits: str
    difficulty: float
    chainwork: str
    nTx: int
    previousblockhash: str
    nextblockhash: str


class Block(BlockHeader):
    strippedsize: int
    size: int
    weight: int
    tx: List[RawTransaction]


@dataclass(kwargs=True, slots=True)
class WalletInfo:
    walletname: str
    walletversion: int
    balance: float
    unconfirmed_balance: float
    immature_balance: float
    txcount: int
    keypoololdest: int
    keypoolsize: int
    keypoolsize_hd_internal: int
    unlocked_until: int
    paytxfee: float
    hdmasterkeyid: str


@dataclass(kwargs=True, slots=True)
class MempoolInfo:

    size: int
    bytes: int
    usage: int
    maxmempool: int
    mempoolminfee: float
    minrelaytxfee: float


@dataclass(kwargs=True, slots=True)
class _NetInfoNetwork:
    name: str
    limited: bool
    reachable: bool
    proxy: str
    proxy_randomize_credentials: bool


@dataclass(kwargs=True, slots=True)
class _NetInfoLocalAddress:
    address: str
    port: int
    score: float


@dataclass(kwargs=True, slots=True)
class NetworkInfo:
    version: int
    subversion: str
    protocolversion: str
    localservices: str
    localservicenames: List[str]
    localrelay: bool
    timeoffset: int
    networkactive: bool
    networks: List[_NetInfoNetwork]
    relayfee: float
    incrementalfee: float
    localaddresses: List[_NetInfoLocalAddress]
    warnings: str


@dataclass(kwargs=True, slots=True)
class _Info:
    difficulty: float
    blocks: int
    warnings: str


class BlockchainInfo(_Info):
    chain: Literal["main", "test", "regtest"]
    headers: int
    bestblockhash: str
    mediantime: int
    verificationprogress: float
    initialblockdownload: bool
    chainwork: str
    size_on_disk: int
    pruned: bool
    softforks: Dict[str, Any]


class ChainTipsStatus(Enum):
    ACTIVE = 'active'
    VALID_FORK = 'valid-fork'
    VALID_HEADERS = 'valid-headers'
    HEADERS_ONLY = 'headers-only'
    INVALID = 'invalid'


@dataclass(kwargs=True, slots=True)
class ChainTipsDetail:
    height: int
    hash: str
    branchlen: int
    status: Literal['active', 'valid-fork', 'valid-headers', 'headers-only', 'invalid']


ChainTips = List[ChainTipsDetail]


@dataclass(kwargs=True, slots=True)
class ChainTxStats:
    time: int
    txcount: int
    window_block_count: int
    window_tx_count: int
    window_interval: int
    txrate: float


@dataclass(kwargs=True, slots=True)
class BlockStats:
    """
    Returned dictionary will contain subset of the following, depending on filtering.
    """

    avgfee: int
    avgfeerate: int
    avgtxsize: int
    blockhash: str
    feerate_percentiles: List[int]
    heigth: int
    ins: int
    maxfee: int
    maxfeerate: int
    maxtxsize: int
    medianfee: int
    mediantime: int
    mediantxsize: int
    minfee: int
    minfeerate: int
    mintxsize: int
    outs: int
    subsidy: int
    swtotal_size: int
    swtotal_weight: int
    swtxs: int
    time: int
    total_out: int
    total_size: int
    total_weight: int
    totalfee: int
    txs: int
    utxo_increase: int
    utxo_size_inc: int


@dataclass(kwargs=True, slots=True)
class MiningInfo:
    networkhashps: float
    pooledtx: int
    chain: Literal["main", "test", "regtest"]


@dataclass(kwargs=True, slots=True)
class NodeInfoAddress:
    address: str
    connected: Literal['inbound', 'outbound']


@dataclass(kwargs=True, slots=True)
class NodeInfo:
    addednode: str
    connected: bool
    addresses: List[NodeInfoAddress]


@dataclass(kwargs=True, slots=True)
class ValidateAddress:
    isvalid: bool
    address: str
    scriptPubKey: str
    ismine: bool
    iswatchonly: bool
    isscript: bool
    iswitness: bool
    pubkey: str
    iscompressed: bool
    account: str
    timestamp: int
    hdkeypath: str
    hdmasterkeyid: str


WalletResponseType = TypeVar(
    "WalletResponseType",
    Difficulty,
    BestBlockHash,
    BlockHash,
    BlockCount,
    NetworkHashps,
    MempoolInfo,
    MiningInfo,
    BlockchainInfo,
    NetworkInfo,
    ChainTips,
    Block,
    BlockStats,
    RawTransaction,
)


class SocketSuccessResponse(TypedDict):
    subscribe: str
    success: bool


class SocketErrorResponse(TypedDict):
    error: str


class SocketDataResponse:
    pass


WebsocketResponseType = TypeVar(
    "WebsocketResponseType",
    SocketSuccessResponse,
    SocketErrorResponse,
)
