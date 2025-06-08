"""Manage project cache directories."""

from __future__ import annotations

import argparse
from pathlib import Path
from helpers.utils import logger
from helpers.tools import tool, SubParser

VENV_WANT = "dev"


BASE_CACHE_DIR = Path(".cache")


def resolve_cache_path(name: str) -> Path:
  """Return path for cache directory *name*."""
  return BASE_CACHE_DIR if name == "default" else BASE_CACHE_DIR / name


def ensure_cache(cache_dir: Path, link: Path) -> None:
  """Create *cache_dir* and symlink *link* to it if needed."""
  if not cache_dir.exists():
    cache_dir.mkdir(parents=True, mode=0o755)
  if not link.exists():
    link.symlink_to(cache_dir)


def ensure_cache_exists(name: str) -> Path:
  """Return path to existing cache directory *name*, or exit."""
  path = resolve_cache_path(name)
  if not path.exists():
    logger.error("Cache directory '%s' not found", name)
    raise SystemExit(1)
  return path


def create_cache(args: argparse.Namespace) -> None:
  """Create a named cache directory with optional parent symlink."""
  cache_path = resolve_cache_path(args.name)

  # Create parent symlink if requested
  if args.symlink_parent and BASE_CACHE_DIR.exists() and not BASE_CACHE_DIR.is_symlink():
    logger.error("Cannot create parent symlink: %s already exists", BASE_CACHE_DIR)
    raise SystemExit(1)

  if args.symlink_parent and not BASE_CACHE_DIR.exists():
    target = Path(args.symlink_parent).expanduser().resolve()
    if not target.exists():
      logger.info("Creating parent cache directory at %s", target)
      target.mkdir(parents=True, mode=0o755)

    logger.info("Symlinking %s -> %s", BASE_CACHE_DIR, target)
    BASE_CACHE_DIR.symlink_to(target)

  # Create the cache directory
  if cache_path.exists() and not args.force:
    logger.info("Cache directory '%s' already exists", args.name)
    return

  logger.info("Creating cache directory '%s'...", args.name)
  cache_path.mkdir(parents=True, mode=0o755, exist_ok=args.force)
  logger.info("Cache directory '%s' created at %s", args.name, cache_path)


def list_caches(args: argparse.Namespace) -> None:
  """List all cache directories."""
  if not BASE_CACHE_DIR.exists():
    logger.info("No cache directories found")
    return

  # Check if base is a symlink
  if BASE_CACHE_DIR.is_symlink():
    target = BASE_CACHE_DIR.resolve()
    print(f"Cache parent: {BASE_CACHE_DIR} -> {target}")
  else:
    print(f"Cache parent: {BASE_CACHE_DIR}")

  if BASE_CACHE_DIR.is_dir():
    caches = []

    subdirs = [d for d in BASE_CACHE_DIR.iterdir() if d.is_dir()]
    if not subdirs:
      caches.append("default")
    else:
      caches.extend(d.name for d in sorted(subdirs))

    if caches:
      print("\nAvailable caches:")
      for cache in caches:
        print(f"  - {cache}")


def clean_cache(args: argparse.Namespace) -> None:
  """Clean cache directory contents."""
  cache_path = ensure_cache_exists(args.name)

  logger.info("Cleaning cache directory '%s'...", args.name)

  count = 0
  for item in cache_path.iterdir():
    if item.is_dir():
      import shutil

      shutil.rmtree(item)
    else:
      item.unlink()
    count += 1

  logger.info("Removed %d items from cache '%s'", count, args.name)


def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("cache", help="Manage cache directories")

  action_parsers = parser.add_subparsers(dest="action", required=True)

  create_parser = action_parsers.add_parser("create", help="Create cache directory")
  create_parser.add_argument(
    "name", default="default", nargs="?", help="Cache directory name (default: 'default')"
  )
  create_parser.add_argument("--force", action="store_true", help="Create even if exists")
  create_parser.add_argument(
    "--symlink-parent", metavar="PATH", help="Create parent .cache as symlink to PATH"
  )
  create_parser.set_defaults(func=create_cache)

  list_parser = action_parsers.add_parser("list", help="List cache directories")
  list_parser.set_defaults(func=list_caches)

  clean_parser = action_parsers.add_parser("clean", help="Clean cache contents")
  clean_parser.add_argument(
    "name", default="default", nargs="?", help="Cache directory name (default: 'default')"
  )
  clean_parser.set_defaults(func=clean_cache)


@tool("cache")
def main(subparsers: SubParser) -> None:
  register(subparsers)

