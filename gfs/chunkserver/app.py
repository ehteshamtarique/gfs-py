import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from gfs.chunkserver.chunkserver import Chunkserver, make_chunkserver
from gfs.chunkserver.heartbeat import heartbeat_loop
from gfs.common.utils import ServerInfo

log = logging.getLogger(__name__)


@dataclass
class AppState:
    chunkserver: Chunkserver
    heartbeat_task: asyncio.Task


def create_app(
    server: ServerInfo,
    master: ServerInfo,
    storage_dir: str | Path = "/tmp/gfs/chunkserver",
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cs = make_chunkserver(server, master, storage_dir)
        task = asyncio.create_task(heartbeat_loop(cs))
        app.state.gfs = AppState(chunkserver=cs, heartbeat_task=task)

        log.info(
            "Chunkserver started. server=%s, master=%s, storage_dir=%s",
            server.server_addr,
            master.server_addr,
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

            log.info("Chunkserver shutdown complete")

    app = FastAPI(title="GFS Chunkserver", lifespan=lifespan)
    return app
