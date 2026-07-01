import httpx

from gfs.common.utils import ServerInfo


async def remote_call(
    server: ServerInfo,
    method: str,
    args: dict,
    timeout: float = 5.0,
) -> dict:
    """POST `method` to `server.ServerAddr` and return the JSON response.

    Each call opens a fresh `httpx.AsyncClient` connection — fine for
    occasional calls like heartbeats, but if you find yourself calling
    this in a hot path, reuse a single client.

    Args:
        server:  Target server. Uses `server.server_addr` (e.g. "10.0.0.1:5000").
        method:  URL path of the endpoint (e.g. "/heartbeat").
        args:    JSON-serializable request body.
        timeout: Per-call timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        httpx.HTTPError:  On connection failure, timeout, or non-2xx status.
    """
    url = f"http://{server.server_addr}{method}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=args)
        response.raise_for_status()
        return response.json()
