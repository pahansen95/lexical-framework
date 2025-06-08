"""Lint code with Ruff."""

from __future__ import annotations

import argparse

VENV_WANT = "dev"

from ..utils import add_common_args, configure_logging, logger, run_command, setup_working_directory


def main(argv: list[str] | None = None) -> None:
  parser = argparse.ArgumentParser(prog="lint")
  add_common_args(parser)
  parser.add_argument("paths", nargs=argparse.REMAINDER, help="Paths to lint")
  args = parser.parse_args(argv)

  configure_logging(args.verbose, args.log_file)

  with setup_working_directory(args):
    logger.debug("paths: %s", args.paths)
    run_command(["ruff", "check", *args.paths])


if __name__ == "__main__":
  main()
