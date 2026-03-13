import argparse
import asyncio
from datetime import datetime

from scraper import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregatore multifonte per bandi su formazione e assistenza digitale."
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=180,
        help="Considera solo elementi pubblicati negli ultimi N giorni.",
    )
    parser.add_argument(
        "--output",
        default=f"bandi_{datetime.now().strftime('%Y%m%d')}.json",
        help="File JSON di output.",
    )
    return parser


async def _main() -> None:
    args = build_parser().parse_args()
    results = await run_pipeline(days_back=args.days_back, output_path=args.output)
    print(f"Trovati {len(results)} bandi pertinenti. Output: {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
