"""Format code with Ruff.

Use ``--check`` to only verify formatting without modifying files.
"""

from __future__ import annotations

import argparse
from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "dev"


def run(args: argparse.Namespace) -> None:
  logger.debug("paths: %s", args.paths)

  cmd = ["ruff", "format"]
  if args.check:
    cmd.append("--check")

  cmd.extend(args.paths)
  run_command(cmd)


@tool("format")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("format", help="Format code with Ruff")
  parser.add_argument(
    "--check",
    action="store_true",
    help="Only verify formatting, do not modify files",
  )
  parser.add_argument("paths", nargs=argparse.REMAINDER, help="Paths to format")
  parser.set_defaults(func=run)

