from __future__ import annotations

import logging
import shlex
import subprocess
import sys

import argparse

from helpers.tools import TOOL_REGISTRY, load_tools
from helpers.utils import add_common_args, configure_logging, setup_working_directory

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="helpers.tool", description="Project helper tools")
  add_common_args(parser)
  subparsers = parser.add_subparsers(dest="tool", required=True)

  load_tools()
  for name, register in sorted(TOOL_REGISTRY.items()):
    register(subparsers)

  return parser


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)

  configure_logging(args.verbose, getattr(args, "log_file", None))

  try:
    with setup_working_directory(args):
      args.func(args)
  except subprocess.CalledProcessError as exc:
    cmd = exc.cmd if isinstance(exc.cmd, str) else " ".join(shlex.quote(a) for a in exc.cmd)
    logger.error("Command failed with exit code %s: %s", exc.returncode, cmd)
    return exc.returncode
  except Exception as exc:  # noqa: BLE001
    logger.error("Unexpected error: %s", exc)
    return 1

  return 0


if __name__ == "__main__":
  sys.exit(main())
