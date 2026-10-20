import asyncio
import os
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


MCP_URL = "http://127.0.0.1:8200/mcp"


async def main():
    token = os.environ.get("MCP_ACCESS_TOKEN")

    if not token:
        raise SystemExit("MCP_ACCESS_TOKEN environment variable is required")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(
            MCP_URL,
            http_client=http_client
        ) as (read_stream, write_stream, _):

            async with ClientSession(
                read_stream,
                write_stream
            ) as session:

                await session.initialize()

                result = await session.list_tools()

                print("\nOFFICER MCP TOOLS")
                for tool in result.tools:
                    print("-", tool.name)

                print("\nTESTING list_applications...")

                result = await session.call_tool(
                    "list_applications",
                    arguments={}
                )

                print(result)


if __name__ == "__main__":
    asyncio.run(main())
    
