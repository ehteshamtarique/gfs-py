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

    def remove_chunk(self) -> None:
        """Delete the chunk's three on-disk files (data + .version +
        .checksum). Does NOT touch the chunkserver's in-memory map —
        the caller (Chunkserver.remove_chunk_and_meta) handles that
        under its own lock. Errors from individual unlink()s are
        ignored (the files may already be gone, or never written)."""
        if self.chunk_path is None:
            return

        self.chunk_path.unlink(missing_ok=True)
        (self.chunk_path.parent / f"{self.chunk_path.name}.version").unlink(missing_ok=True)
        (self.chunk_path.parent / f"{self.chunk_path.name}.checksum").unlink(missing_ok=True)
