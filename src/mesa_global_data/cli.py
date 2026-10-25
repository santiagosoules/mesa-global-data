from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from .api import serve
from .bootstrap import bootstrap_from_bundle
from .exporter import export_all
from .pipeline import collect_all, utc_now
from .storage import Storage
from .validation import validate_storage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mesa Global institutional data pipeline")
    parser.add_argument("--db", default="data/mesa_global.sqlite", help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Fetch, normalize, validate, store and export")
    collect.add_argument("--export-dir", default="data/exports")
    collect.add_argument(
        "--profile", choices=("daily", "h41", "weekly", "all"), default="all",
        help="daily=Treasury/NY Fed/OFR, h41=Federal Reserve H.4.1, weekly=CFTC",
    )

    validate = subparsers.add_parser("validate", help="Validate latest stored observations")
    validate.add_argument("--reference-date")

    export = subparsers.add_parser("export", help="Write JSON artifacts for site integration")
    export.add_argument("--export-dir", default="data/exports")

    bootstrap = subparsers.add_parser("bootstrap", help="Restore private runtime storage from public JSON history")
    bootstrap.add_argument("--bundle", default="public/site_bundle.json")

    api = subparsers.add_parser("serve", help="Serve the read-only integration API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8787)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "collect":
        result = collect_all(args.db, args.export_dir, profile=args.profile)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "ok" else 1
    if args.command == "validate":
        storage = Storage(args.db)
        try:
            result = validate_storage(storage, args.reference_date)
        finally:
            storage.close()
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "ok" else 1
    if args.command == "export":
        storage = Storage(args.db)
        try:
            paths = export_all(storage, args.export_dir, utc_now())
        finally:
            storage.close()
        print(json.dumps(paths, indent=2, sort_keys=True))
        return 0
    if args.command == "bootstrap":
        storage = Storage(args.db)
        try:
            result = bootstrap_from_bundle(storage, args.bundle)
        finally:
            storage.close()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "serve":
        serve(args.db, args.host, args.port)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

