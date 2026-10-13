import asyncio

from mcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()

        print()
        print("TOOLS FOUND:")
        for tool in tools:
            print("-", tool.name)

        result = await client.call_tool(
            "summarize_overdue_invoices",
            {},
        )

        print()
        print("OVERDUE SUMMARY:")
        print(result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
