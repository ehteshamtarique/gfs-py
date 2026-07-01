import asyncio
import logging

from gfs.chunkserver.chunkserver import Chunkserver, send_heartbeat
from gfs.settings import HEARTBEAT_INTERVAL

log = logging.getLogger(__name__)


async def heartbeat_loop(chunkserver: Chunkserver) -> None:
    interval = HEARTBEAT_INTERVAL.total_seconds()

    log.info("heartbeat loop started (interval=%.3fs)", interval)

    try:
        while True:
            try:
                await send_heartbeat(chunkserver)
            except Exception:
                log.exception("heartbeat iteration failed")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        log.info("heartbeat loop stopped")
        raise
