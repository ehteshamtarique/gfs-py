import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request

from gfs.common.constants import Namespace, ServerType
from gfs.common.heartbeat import HeartBeatArgs, HeartBeatReply
from gfs.common.utils import ServerInfo
from gfs.master.metadata import Master, make_master
from gfs.master.periodic import periodic_check

log = logging.getLogger(__name__)


@dataclass
class AppState:
    master: Master
    periodic_task: asyncio.Task


def create_app(
    server: ServerInfo | None = None,
    storage_dir: str = "/tmp/gfs",
) -> FastAPI:
    if server is None:
        server = ServerInfo(
            server_type=ServerType.MASTER,
            server_addr="0.0.0.0:5000",
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        master = make_master(server, storage_dir)
        task = asyncio.create_task(periodic_check(master))
        app.state.gfs = AppState(master=master, periodic_task=task)

        log.info(
            "Master started. server=%s, storage_dir=%s",
            server.server_addr,
            storage_dir,
        )

        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            log.info("Master shutdown complete")

    app = FastAPI(title="GFS Master", lifespan=lifespan)

    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    @app.post("/heartbeat", response_model=HeartBeatReply)
    async def heartbeat(request: Request, args: HeartBeatArgs) -> HeartBeatReply:
        """Receive heartbeat from a chunkserver. Registers new
        chunkservers, updates ChunkMetadata.servers based on reported
        versions, and returns the list of chunks the chunkserver should
        drop (because the master has a newer version)."""
        state: AppState = request.app.state.gfs
        master: Master = state.master
        server = args.server_info

        with master.chunkservers_lock.gen_wlock():
            if server not in master.chunkservers:
                log.info("new chunkserver %s joined", server)
                master.chunkservers.add(server)

        expired_chunks: list = []

        for chunk_info in args.chunks:
            with master.chunks_lock.gen_wlock():
                chunk_meta = master.chunks.get(chunk_info.handle)

                if chunk_meta is None:
                    log.info(
                        "chunk %s reported by %s but not on master, ignore",
                        chunk_info.handle,
                        server,
                    )
                    continue

                if chunk_info.version < chunk_meta.version:
                    log.info(
                        "chunk %s version %d is stale (master has %d), ignore",
                        chunk_info.handle,
                        chunk_info.version,
                        chunk_meta.version,
                    )
                    expired_chunks.append(chunk_info.handle)
                    chunk_meta.remove_chunkserver(server)
                else:
                    chunk_meta.add_chunkserver(server)

        return HeartBeatReply(expired_chunks=expired_chunks)

    @app.post("/files/create")
    async def create_file(request: Request) -> dict:
        """Create a file. Real impl: lock ancestors, allocate initial chunk,
        pick NUMBER_OF_REPLICAS chunkservers, instruct them to create the chunk."""
        # TODO: full create handler
        return {"status": "ok"}

    @app.get("/files/info")
    async def file_info(request: Request) -> dict:
        """Return FileMetadata for a path. Real impl: look up
        master.namespaces[ns].files[path], return chunk handle list."""
        # TODO: full info handler
        return {"chunks": []}

    @app.post("/chunks/append")
    async def append(request: Request) -> dict:
        """Record-append. Real impl: pick primary chunkserver, grant lease,
        return primary + secondaries to client."""
        # TODO: full append handler
        return {"status": "ok"}


app = create_app()
