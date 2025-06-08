"""Build or serve documentation."""

from __future__ import annotations

import argparse
from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "docs"


def run(args: argparse.Namespace) -> None:
  logger.debug("docs action: %s", args.action)
  if args.action == "build":
    run_command("mkdocs build")
  else:
    run_command("mkdocs serve")


@tool("docs")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("docs", help="Build or serve documentation")
  parser.add_argument("action", choices=["build", "serve"])
  parser.set_defaults(func=run)

