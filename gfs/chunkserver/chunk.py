from dataclasses import dataclass, field
from pathlib import Path

from readerwriterlock import rwlock

from gfs.chunkserver.checksum import Checksum
from gfs.common.constants import ChunkHandle, ChunkVersion


@dataclass
class Chunk:
    handle: ChunkHandle
    version: ChunkVersion = 0
    length: int = 0
    chunk_path: Path | None = None
    checksum: int = 0
    lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )

    def read(self) -> bytes:
        with self.lock.gen_rlock():
            if self.chunk_path is None:
                raise ValueError("chunk_path is not set")
            return self.chunk_path.read_bytes()

    def verify(self) -> bool:
        return Checksum(self.checksum).check(self.read())
