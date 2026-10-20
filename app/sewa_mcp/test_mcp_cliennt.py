import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    token = os.environ["MCP_ACCESS_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    async with streamable_http_client(
        "http://127.0.0.1:8100/mcp",
        headers=headers,
    ) as (read_stream, write_stream, _):

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.list_tools()

            print("Available citizen tools:")
            for tool in result.tools:
                print("-", tool.name)

            result = await session.call_tool(
                "get_scheme_info",
                arguments={},
            )

            print("\nget_scheme_info result:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())