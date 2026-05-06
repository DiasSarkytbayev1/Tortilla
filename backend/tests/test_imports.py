"""
Smoke test: every top-level module under app/ imports cleanly.

Catches path-rename mistakes after the restructure (e.g., a stale `from etl
import ...` left over from the pre-restructure layout).
"""

import importlib

MODULES = [
    "app",
    "app.config",
    "app.db",
    "app.main",
    "app.cli",
    "app.api",
    "app.analytics",
    "app.analytics.queries",
    "app.etl",
    "app.etl.load",
    "app.etl.generate",
]


def test_modules_import():
    for name in MODULES:
        importlib.import_module(name)


def test_cli_parser_builds():
    from app.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["analytics", "best_sellers", "2026-05-01", "2026-05-31"])
    assert args.command == "analytics"
    assert args.query == "best_sellers"
    assert args.from_date == "2026-05-01"
    assert args.to_date == "2026-05-31"
