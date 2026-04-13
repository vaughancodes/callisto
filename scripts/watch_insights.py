#!/usr/bin/env python3
"""Watch real-time insights from the broadcaster WebSocket."""

import asyncio
import json
import sys

import websockets

URL = sys.argv[1] if len(sys.argv) > 1 else "wss://callisto.vaughan.codes/ws/calls/live"


async def watch():
    print(f"Connecting to {URL}...")
    async with websockets.connect(URL) as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "insight":
                print(f"\n[{data['severity']}] {data['template_name']}: {data['confidence']:.0%}")
                print(f"  {data['evidence']}")
            else:
                print(data)


asyncio.run(watch())
