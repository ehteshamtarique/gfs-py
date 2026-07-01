import asyncio
import logging

from gfs.master.metadata import Master
from gfs.settings import PERIODIC_WORK_INTERVAL

log = logging.getLogger(__name__)


async def periodic_check(master: Master) -> None:
    interval = PERIODIC_WORK_INTERVAL.total_seconds()

    log.info("periodic_check started (interval=%.0fs)", interval)

    try:
        while True:
            await asyncio.sleep(interval)

            try:
                _garbage_collect(master)
                _re_replicate(master)
                _rebalance(master)
            except Exception:
                log.exception("periodic_check iteration failed")
    except asyncio.CancelledError:
        log.info("periodic_check stopped")
        raise


def _garbage_collect(master: Master) -> None:
    # TODO: find chunks with ref_count == 0 and no live path;
    # instruct the chunkservers in `servers` to delete them.
    pass


def _re_replicate(master: Master) -> None:
    # TODO: for each chunk with fewer than NUMBER_OF_REPLICAS replicas,
    # pick new chunkservers and instruct them to copy the chunk.
    pass


def _rebalance(master: Master) -> None:
    # TODO: move replicas between chunkservers to balance disk usage.
    pass
