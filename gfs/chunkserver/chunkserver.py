import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from readerwriterlock import rwlock

from gfs.chunkserver.chunk import Chunk
from gfs.common.client import remote_call
from gfs.common.constants import ChunkHandle
from gfs.common.heartbeat import ChunkInfo, HeartBeatArgs, HeartBeatReply
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
            log.warning("checksum mismatch for chunk %s, deleting", handle)
            chunk.remove_chunk()
            return None
    except OSError as e:
        log.warning("failed to read chunk %s: %s", handle, e)
        return None

    return chunk


def remove_chunk_and_meta(chunkserver: Chunkserver, handle: ChunkHandle) -> bool:
    """Remove a chunk from the in-memory map and delete its on-disk
    files. Returns True if the chunk was found and removed, False if
    the chunkserver didn't have it.

    Lock pattern: take the write lock, pop the entry, release the
    lock, then call chunk.remove_chunk() for the disk I/O. This
    avoids reentrancy (readerwriterlock isn't reentrant) and keeps
    the critical section short.
    """
    with chunkserver.chunks_lock.gen_wlock():
        chunk = chunkserver.chunks.pop(handle, None)

    if chunk is None:
        return False

    chunk.remove_chunk()
    return True


async def send_heartbeat(chunkserver: Chunkserver) -> None:
    """Build a HeartBeatArgs from the current chunk state and send it to
    the master. Two-tier locking: read-lock the chunks map, then
    read-lock each chunk while copying its (version, handle, length)."""
    chunks_info: list[ChunkInfo] = []

    with chunkserver.chunks_lock.gen_rlock():
        for chunk in chunkserver.chunks.values():
            with chunk.lock.gen_rlock():
                chunks_info.append(
                    ChunkInfo(
                        version=chunk.version,
                        handle=chunk.handle,
                        length=chunk.length,
                    )
                )

    args = HeartBeatArgs(
        server_info=chunkserver.server,
        chunks=chunks_info,
    )

    try:
        reply_data = await remote_call(
            server=chunkserver.master,
            method="/heartbeat",
            args=args.model_dump(mode="json"),
        )
    except httpx.HTTPError as e:
        log.warning(
            "heartbeat to %s failed: %s",
            chunkserver.master.server_addr,
            e,
        )
        return

    reply = HeartBeatReply.model_validate(reply_data)

    for expired_handle in reply.expired_chunks:
        if remove_chunk_and_meta(chunkserver, expired_handle):
            log.info(
                "dropped stale chunk %s per master's heartbeat reply",
                expired_handle,
            )
        else:
            log.warning(
                "master told us to drop chunk %s but we don't have it",
                expired_handle,
            )
