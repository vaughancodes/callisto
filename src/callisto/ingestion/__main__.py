"""Allow running the ingestion server as: python -m callisto.ingestion.server"""

import asyncio

from callisto.ingestion.server import main

asyncio.run(main())
