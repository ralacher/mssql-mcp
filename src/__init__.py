from . import server
import asyncio
import logging
import sys

logger = logging.getLogger('mcp_mssql_server')

def main():
    try:
        asyncio.run(server.main())
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        sys.exit(1)

__all__ = ["main", "server"]