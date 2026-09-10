import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def tools_by_name(app):
    """name -> Tool for a FastMCP server.

    fastmcp 4 replaced ``FastMCP.get_tools()`` (dict) with ``list_tools()`` (list);
    the tests only ever wanted the mapping, so keep that shape here.
    """
    return {t.name: t for t in await app.list_tools()}
