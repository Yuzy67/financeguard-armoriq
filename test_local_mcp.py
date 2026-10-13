import asyncio

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    server = StdioServerParameters(
        command="python",
        args=["finance_mcp/server.py"],
    )

    async with stdio_client(server) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()

            print()
            print("TOOLS FOUND:")
            for tool in tools.tools:
                print("-", tool.name)

            result = await session.call_tool(
                "summarize_overdue_invoices",
                arguments={},
            )

            print()
            print("OVERDUE SUMMARY:")
            for item in result.content:
                print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
