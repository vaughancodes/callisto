"""WebSocket broadcaster for real-time insight delivery to dashboards.

Clients connect to /ws/calls/{call_id}/live to receive insights for a specific
call, or /ws/calls/live to receive insights for all calls.

The broadcaster subscribes to Redis Pub/Sub channels and forwards messages
to connected WebSocket clients.

Run directly:
    python -m callisto.broadcaster.server

In Docker Compose this runs as its own service.
"""

import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
import websockets

from callisto.config import Config

logger = logging.getLogger(__name__)

LISTEN_HOST = os.environ.get("BROADCASTER_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("BROADCASTER_PORT", "5311"))

# Connected clients: {call_id: set(websocket)} and {"all": set(websocket)}
_clients: dict[str, set] = {"all": set()}
_clients_lock = asyncio.Lock()


async def handle_dashboard_ws(websocket):
    """Handle a dashboard WebSocket connection.

    Path determines what insights the client receives:
      /ws/calls/{call_id}/live  — insights for a specific call
      /ws/calls/live            — insights for all calls
    """
    path = websocket.request.path if hasattr(websocket, 'request') else ""

    # Parse call_id from path
    # /ws/calls/{call_id}/live or /ws/calls/live
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "ws" and parts[1] == "calls" and parts[3] == "live":
        call_id = parts[2]
    else:
        call_id = "all"

    async with _clients_lock:
        if call_id not in _clients:
            _clients[call_id] = set()
        _clients[call_id].add(websocket)

    client_count = sum(len(s) for s in _clients.values())
    logger.info(
        "Dashboard connected: call_id=%s (%d total clients)",
        call_id, client_count,
    )

    # Send a welcome message
    await websocket.send(json.dumps({
        "type": "connected",
        "watching": call_id,
    }))

    try:
        # Keep connection alive — clients are read-only, we just wait
        async for message in websocket:
            # Clients can send ping/pong or filter updates
            try:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        async with _clients_lock:
            if call_id in _clients:
                _clients[call_id].discard(websocket)
                if not _clients[call_id] and call_id != "all":
                    del _clients[call_id]

        logger.info("Dashboard disconnected: call_id=%s", call_id)


async def redis_subscriber():
    """Subscribe to Redis Pub/Sub and forward insights to connected clients."""
    redis_url = os.environ.get("REDIS_URL", Config.REDIS_URL)
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()

    # Subscribe to all insight channels via pattern
    await pubsub.psubscribe("insights:*")
    logger.info("Subscribed to insights:* channels")

    async for message in pubsub.listen():
        if message["type"] not in ("pmessage",):
            continue

        channel = message["channel"]  # e.g. "insights:{call_id}" or "insights:all"
        data = message["data"]

        try:
            insight = json.loads(data)
        except json.JSONDecodeError:
            continue

        call_id = insight.get("call_id", "")

        if channel == "insights:all":
            # Global channel → only send to clients watching all calls
            await _broadcast_to_clients("all", data)
        else:
            # Per-call channel → only send to clients watching that specific call
            await _broadcast_to_clients(call_id, data)


async def _broadcast_to_clients(key: str, message: str):
    """Send a message to all WebSocket clients watching the given key."""
    async with _clients_lock:
        clients = _clients.get(key, set()).copy()

    if not clients:
        return

    stale = set()
    for ws in clients:
        try:
            await ws.send(message)
        except websockets.exceptions.ConnectionClosed:
            stale.add(ws)

    if stale:
        async with _clients_lock:
            if key in _clients:
                _clients[key] -= stale


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger.info("Starting insight broadcaster on %s:%d", LISTEN_HOST, LISTEN_PORT)

    # Run WebSocket server and Redis subscriber concurrently
    async with websockets.serve(
        handle_dashboard_ws,
        LISTEN_HOST,
        LISTEN_PORT,
        max_size=2**16,
    ):
        await redis_subscriber()


if __name__ == "__main__":
    asyncio.run(main())
