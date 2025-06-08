"""Lint code with Ruff."""

from __future__ import annotations

import argparse
from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "dev"


def run(args: argparse.Namespace) -> None:
  """Run ruff check, fixing issues unless ``--dry-run`` was passed."""

  logger.debug("paths: %s", args.paths)

  cmd = ["ruff", "check"]
  if not args.dry_run:
    cmd.append("--fix")

  cmd.extend(args.paths)
  run_command(cmd)


@tool("lint")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("lint", help="Lint code with Ruff")
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Only check, do not apply fixes",
  )
  parser.add_argument("paths", nargs=argparse.REMAINDER, help="Paths to lint")
  parser.set_defaults(func=run)

