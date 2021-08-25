from core.types import (
    BHeightType,
    BlockHash,
)


class Block:
    best_block_height: BHeightType = 0

    __slots__ = ('_hash', 'height', 'time', 'mediantime')

    def __init__(self, bl_hash, height, **data):
        self._hash: BlockHash = bl_hash
        self.height: BHeightType = height
        self.time: int = data.get('time')
        self.mediantime: int = data.get('mediantime')

        if height > Block.best_block_height:
            Block.best_block_height = height

    @classmethod
    async def create_block(cls, block_hash: str, height: int, **data) -> "Block":

        cls._hash = block_hash
        cls.height = height
        return b

    def __hash__(self):
        return self._hash

    def __repr__(self):
        return f'<Block {self.count} {hash(self)}>'


class Tx:

    @classmethod
    async def create_tx(cls):
        return cls()

