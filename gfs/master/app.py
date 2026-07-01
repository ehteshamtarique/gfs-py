import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request

from gfs.common.constants import Namespace, ServerType
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
    @app.post("/heartbeat")
    async def heartbeat(request: Request) -> dict:
        """Chunkserver heartbeat. Real impl: update last_seen, add new
        chunkservers to master.chunkservers, update ChunkMetadata.servers."""
        # TODO: full heartbeat handler
        return {"status": "ok"}

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
