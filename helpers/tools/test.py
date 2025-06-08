"""Run tests."""

from __future__ import annotations

import argparse
from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "test"


def run(args: argparse.Namespace) -> None:
  logger.debug("extra args: %s", args.extra)
  run_command(["pytest", *args.extra])


@tool("test")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("test", help="Run tests")
  parser.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args for pytest")
  parser.set_defaults(func=run)

