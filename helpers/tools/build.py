"""Build distribution packages."""

from __future__ import annotations

import argparse
from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "dev"


def run(args: argparse.Namespace) -> None:
  logger.debug("extra args: %s", args.extra)
  run_command(["uv", "build", *args.extra])


@tool("build")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("build", help="Build distribution packages")
  parser.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args for uv build")
  parser.set_defaults(func=run)



