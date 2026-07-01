from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from readerwriterlock import rwlock

from gfs.common.constants import (
    ChunkHandle,
    ChunkVersion,
    Namespace,
)
from gfs.common.utils import (
    PathInfo,
    ServerInfo,
)


@dataclass
class FileMetadata:
    chunks: list[ChunkHandle] = field(
        default_factory=list,
    )

    lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )


@dataclass
class ChunkMetadata:
    lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )

    # Persistent data
    version: ChunkVersion = 0
    ref_count: int = 0

    lease_holder: Optional[ServerInfo] = None
    lease_expire: Optional[datetime] = None

    # In-memory data
    servers: dict[ServerInfo, bool] = field(
        default_factory=dict,
    )

    def add_chunkserver(self, server: ServerInfo) -> None:
        with self.lock.gen_wlock():
            self.servers[server] = True

    def remove_chunkserver(self, server: ServerInfo) -> None:
        with self.lock.gen_wlock():
            self.servers.pop(server, None)


class NamespaceMetadata:
    def __init__(self) -> None:
        # path -> file metadata
        self.files: dict[
            PathInfo,
            FileMetadata,
        ] = {}

        self.files_lock = rwlock.RWLockFair()

        # path string -> directory
        self.directories: dict[
            str,
            PathInfo,
        ] = {}

        self.directories_lock = rwlock.RWLockFair()

        # path string -> RW lock
        self.locks: dict[
            str,
            rwlock.RWLockFair,
        ] = {}

        # path string -> currently held read/write lock
        self.active_locks: dict[
            str,
            rwlock.Lockable,
        ] = {}

        self.locks_lock = rwlock.RWLockFair()

    def lock_file_or_directory(
        self,
        pathname: str,
        read_only: bool = True,
    ) -> None:
        with self.locks_lock.gen_rlock():
            rw_lock = self.locks.get(pathname)

        if rw_lock is None:
            return

        if read_only:
            lock = rw_lock.gen_rlock()
        else:
            lock = rw_lock.gen_wlock()

        lock.acquire()

        with self.locks_lock.gen_wlock():
            self.active_locks[pathname] = lock

    def unlock_file_or_directory(
        self,
        pathname: str,
    ) -> None:
        with self.locks_lock.gen_wlock():
            lock = self.active_locks.pop(pathname, None)

        if lock is not None:
            lock.release()

    def lock_ancestors(
        self,
        path_info: PathInfo,
    ) -> bool:
        try:
            parent = path_info.parent()
        except Exception:
            return False

        pathname = parent.pathname

        ancestors: list[str] = []

        with self.locks_lock.gen_rlock():
            for index, char in enumerate(pathname):
                if index != 0 and char == "/":
                    ancestor = pathname[:index]
                    if ancestor in self.locks:
                        ancestors.append(ancestor)

        for ancestor in ancestors:
            self.lock_file_or_directory(
                ancestor,
                read_only=True,
            )

        return True


@dataclass
class Master:
    server: ServerInfo
    storage_dir: str

    # namespace name -> namespace metadata
    namespaces: dict[
        Namespace,
        NamespaceMetadata,
    ] = field(
        default_factory=dict,
    )

    namespaces_lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )

    # chunk handle -> chunk metadata
    chunks: dict[
        ChunkHandle,
        ChunkMetadata,
    ] = field(
        default_factory=dict,
    )

    chunks_lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )

    # known chunkservers (set, not list — needs O(1) membership tests
    # during heartbeat processing)
    chunkservers: set[ServerInfo] = field(
        default_factory=set,
    )

    chunkservers_lock: rwlock.RWLockFair = field(
        default_factory=rwlock.RWLockFair,
    )


def make_master(
    server: ServerInfo,
    storage_dir: str,
) -> Master:
    return Master(
        server=server,
        storage_dir=storage_dir,
    )