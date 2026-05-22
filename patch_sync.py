import sys

file_path = "apps/backend-rag/scripts/sync_shortcuts_to_individual.py"
with open(file_path, "r") as f:
    content = f.read()

content = content.replace("LIMIT $1", "LIMIT $1 OFFSET $2")
content = content.replace("limit,", "limit, offset,")

content = content.replace("parser.add_argument(\"--limit\", type=int, default=5000", "parser.add_argument(\"--limit\", type=int, default=5000)\n    parser.add_argument(\"--offset\", type=int, default=0")

content = content.replace("asyncio.run(main(args.dry_run, args.limit))", "asyncio.run(main(args.dry_run, args.limit, args.offset))")
content = content.replace("async def main(dry_run: bool, limit: int) -> None:", "async def main(dry_run: bool, limit: int, offset: int) -> None:")

with open(file_path, "w") as f:
    f.write(content)
