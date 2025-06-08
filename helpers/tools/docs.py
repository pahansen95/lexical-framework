"""Build or serve documentation."""

from __future__ import annotations

import argparse

VENV_WANT = "docs"

from ..utils import add_common_args, configure_logging, logger, run_command, setup_working_directory


def main(argv: list[str] | None = None) -> None:
  parser = argparse.ArgumentParser(prog="docs")
  add_common_args(parser)
  parser.add_argument("action", choices=["build", "serve"])
  args = parser.parse_args(argv)

  configure_logging(args.verbose, args.log_file)

  with setup_working_directory(args):
    logger.debug("docs action: %s", args.action)
    if args.action == "build":
      run_command("mkdocs build")
    else:
      run_command("mkdocs serve")


if __name__ == "__main__":
  main()
