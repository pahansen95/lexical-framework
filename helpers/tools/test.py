"""Run tests."""

from __future__ import annotations

import argparse

VENV_WANT = "test"

from ..utils import add_common_args, configure_logging, logger, run_command, setup_working_directory


def main(argv: list[str] | None = None) -> None:
  parser = argparse.ArgumentParser(prog="test")
  add_common_args(parser)
  parser.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args for pytest")
  args = parser.parse_args(argv)

  configure_logging(args.verbose, args.log_file)

  with setup_working_directory(args):
    logger.debug("extra args: %s", args.extra)
    run_command(["pytest", *args.extra])


if __name__ == "__main__":
  main()
