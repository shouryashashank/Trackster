"""Command-line entry for Trackpod (headless) — `trackpod` or `python -m trackpod`."""

from __future__ import annotations

import argparse
import sys

from trackpod.core import pipeline
from trackpod.core.config import Settings, user_data_dir
from trackpod.core.db import Database


def _open_db(args) -> Database:
    db = Database()
    db.init()
    return db


def cmd_init(_args) -> int:
    db = Database()
    db.init()
    print(f"Initialized library at: {user_data_dir()}")
    return 0


def cmd_paths(_args) -> int:
    print(f"data dir: {user_data_dir()}")
    print(f"library db: {user_data_dir() / 'library.db'}")
    print(f"default music folder: {Settings(None).library_folder}")
    return 0


def _settings_from(db: Database) -> Settings:
    return Settings(db.settings_store())


def cmd_settings(args) -> int:
    db = _open_db(args)
    settings = _settings_from(db)
    if args.set:
        for kv in args.set:
            if "=" not in kv:
                print(f"skip malformed '{kv}' (use key=value)")
                continue
            key, _, value = kv.partition("=")
            settings.set(key.strip(), value.strip())
            print(f"set {key.strip()}={value.strip()}")
    print(f"enable_saavn={settings.enable_saavn}")
    print(f"saavn_fallback_youtube={settings.saavn_fallback_youtube}")
    print(f"concurrency={settings.concurrency}")
    print(f"library_folder={settings.library_folder}")
    return 0


def cmd_add_source(args) -> int:
    db = _open_db(args)
    source = pipeline.ingest_source(db, args.url, kind=args.kind, name=args.name)
    with db.session() as session:
        source = session.merge(source)
        print(f"source #{source.id}: {source.kind} {source.external_ref}")
        for item in source.items:
            print(f"  - {item.title or '?'} :: {item.artist or '?'}")
    return 0


def cmd_resolve(args) -> int:
    db = _open_db(args)
    settings = _settings_from(db)
    sources = pipeline.list_sources(db, args.source_id)
    made = 0
    for src in sources:
        made += len(pipeline.ensure_tracks(db, src, settings))
    print(f"resolved {made} new tracks (total: {pipeline.count_tracks(db)})")
    return 0


def cmd_download(args) -> int:
    db = _open_db(args)
    settings = _settings_from(db)
    paths = pipeline.download_tracks(db, settings)
    print(f"downloaded {len(paths)} file(s)")
    return 0


def cmd_gui(_args) -> int:
    from trackpod.ui.app import run_application

    return run_application()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trackpod", description="Trackpod music manager")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("init", help="create the library database & data dir")
    sub.add_parser("paths", help="show data paths")

    sp = sub.add_parser("settings", help="read/write settings")
    sp.add_argument("--set", action="append", metavar="key=value", help="set a setting")

    add = sub.add_parser("add-source", help="add a playlist/artist URL as a source")
    add.add_argument("url", help="source URL (spotify/apple/youtube)")
    add.add_argument("--kind", choices=["spotify", "youtube", "apple"], help="override kind")
    add.add_argument("--name", help="display name")

    res = sub.add_parser("resolve", help="resolve source items into tracks")
    res.add_argument("--source-id", type=int, help="only this source id")

    sub.add_parser("download", help="download pending tracks")

    sub.add_parser("gui", help="open the desktop UI (PySide6)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "paths":
        return cmd_paths(args)
    if args.command == "settings":
        return cmd_settings(args)
    if args.command == "add-source":
        return cmd_add_source(args)
    if args.command == "resolve":
        return cmd_resolve(args)
    if args.command == "download":
        return cmd_download(args)
    if args.command == "gui":
        return cmd_gui(args)
    build_parser().print_help()
    return 0 if args.command else 1


if __name__ == "__main__":
    sys.exit(main())
