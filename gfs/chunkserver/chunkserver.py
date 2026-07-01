import logging
from dataclasses import dataclass, field
from pathlib import Path

from readerwriterlock import rwlock

from gfs.chunkserver.chunk import Chunk
from gfs.common.constants import ChunkHandle
from gfs.common.utils import ServerInfo

log = logging.getLogger(__name__)


@dataclass
class Chunkserver:
    server: ServerInfo
    master: ServerInfo
    storage_dir: Path
    chunks_dir: Path
    leases_dir: Path

    chunks: dict[ChunkHandle, Chunk] = field(
        default_factory=dict,
    )

    chunks_lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )


def make_chunkserver(
    server: ServerInfo,
    master: ServerInfo,
    storage_dir: str | Path,
) -> Chunkserver:
    storage_path = Path(storage_dir)
    chunkserver = Chunkserver(
        server=server,
        master=master,
        storage_dir=storage_path,
        chunks_dir=storage_path / "chunks",
        leases_dir=storage_path / "leases",
    )
    chunkserver.chunks_dir.mkdir(parents=True, exist_ok=True)
    chunkserver.leases_dir.mkdir(parents=True, exist_ok=True)
    load_chunks(chunkserver)
    return chunkserver


def load_chunks(chunkserver: Chunkserver) -> None:
    if not chunkserver.chunks_dir.exists():
        return

    for file in chunkserver.chunks_dir.iterdir():
        if file.is_dir():
            continue
        if file.suffix in (".version", ".checksum"):
            continue

        try:
            handle = int(file.name)
        except ValueError:
            log.warning("skipping non-chunk file: %s", file.name)
            continue

        chunk = load_chunk_metadata(handle, chunkserver)
        if chunk is None:
            log.warning("chunk %s is corrupted, skipping", handle)
            continue

        chunkserver.chunks[handle] = chunk


def load_chunk_metadata(
    handle: ChunkHandle,
    chunkserver: Chunkserver,
) -> Chunk | None:
    version_path = chunkserver.chunks_dir / f"{handle}.version"
    checksum_path = chunkserver.chunks_dir / f"{handle}.checksum"
    chunk_path = chunkserver.chunks_dir / f"{handle}"

    if (
        not version_path.exists()
        or not checksum_path.exists()
        or not chunk_path.exists()
    ):
        log.warning("missing metadata files for chunk %s", handle)
        return None

    try:
        version = int(version_path.read_text().strip())
        checksum = int(checksum_path.read_text().strip())
    except (ValueError, OSError) as e:
        log.warning("failed to parse metadata for chunk %s: %s", handle, e)
        return None

    chunk = Chunk(
        handle=handle,
        version=version,
        length=chunk_path.stat().st_size,
        chunk_path=chunk_path,
        checksum=checksum,
    )

    try:
        if not chunk.verify():
            log.warning("checksum mismatch for chunk %s", handle)
            return None
    except OSError as e:
        log.warning("failed to read chunk %s: %s", handle, e)
        return None

    return chunk
