"""
Unified CLI entry point.

Usage:
    python -m app.cli generate [DATE]
    python -m app.cli etl      [DATE] [EXPORTS_ROOT]
    python -m app.cli analytics best_sellers FROM TO [--restaurant_id N] [--category C] [--top_n N]
    python -m app.cli analytics peak_hours   FROM TO [--restaurant_id N]
    python -m app.cli analytics comparison   FROM TO

Inside the Docker stack, run via:
    docker compose run --rm backend python -m app.cli <command>
"""

import argparse
import sys
import textwrap


def _cmd_generate(args: argparse.Namespace) -> None:
    from app.etl.generate import generate_exports

    generate_exports(args.date, args.exports_root)


def _cmd_etl(args: argparse.Namespace) -> None:
    from app.etl.load import run_etl

    run_etl(args.date, args.exports_root)


def _cmd_analytics(args: argparse.Namespace) -> None:
    from app.analytics.queries import best_sellers, peak_hours, restaurant_comparison

    if args.query == "best_sellers":
        best_sellers(
            args.from_date,
            args.to_date,
            restaurant_id=args.restaurant_id,
            category=args.category,
            top_n=args.top_n,
        )
    elif args.query == "peak_hours":
        peak_hours(args.from_date, args.to_date, restaurant_id=args.restaurant_id)
    elif args.query == "comparison":
        restaurant_comparison(args.from_date, args.to_date)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Tortilla Analytics CLI — generate mock POS data, run ETL, and execute analytical queries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python -m app.cli generate 2026-05-04
              python -m app.cli etl 2026-05-04
              python -m app.cli analytics best_sellers 2026-05-01 2026-05-31
              python -m app.cli analytics best_sellers 2026-05-01 2026-05-31 --restaurant_id 2 --top_n 5
              python -m app.cli analytics peak_hours   2026-05-01 2026-05-31 --restaurant_id 3
              python -m app.cli analytics comparison   2026-05-01 2026-05-31
        """),
    )
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate mock POS export CSVs for a date.")
    g.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: today UTC)")
    g.add_argument("--exports_root", default=None, help="Override POS_EXPORTS_DIR for this run.")
    g.set_defaults(func=_cmd_generate)

    e = sub.add_parser("etl", help="Load POS export CSVs for a date into PostgreSQL.")
    e.add_argument("date", nargs="?", default=None, help="YYYY-MM-DD (default: today UTC)")
    e.add_argument("--exports_root", default=None, help="Override POS_EXPORTS_DIR for this run.")
    e.set_defaults(func=_cmd_etl)

    a = sub.add_parser("analytics", help="Run an analytical query.")
    a.add_argument("query", choices=["best_sellers", "peak_hours", "comparison"])
    a.add_argument("from_date", help="Start date YYYY-MM-DD (inclusive)")
    a.add_argument("to_date", help="End date YYYY-MM-DD (inclusive)")
    a.add_argument("--restaurant_id", type=int, default=None)
    a.add_argument("--category", type=str, default=None, help="Menu category filter (best_sellers only).")
    a.add_argument("--top_n", type=int, default=10, help="Row count for best_sellers (default 10).")
    a.set_defaults(func=_cmd_analytics)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
