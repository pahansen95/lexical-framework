"""Utility functions for helpers."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Generator, Sequence

logger = logging.getLogger(__name__)


def configure_logging(verbosity: int = 0, log_file: str | None = None) -> None:
  """Configure basic logging for helper scripts."""
  level = logging.WARNING - (10 * verbosity)
  if level < logging.DEBUG:
    level = logging.DEBUG

  handlers: list[logging.Handler] = [logging.StreamHandler()]
  if log_file:
    handlers.append(logging.FileHandler(log_file))

  logging.basicConfig(
    level=level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=handlers,
    force=True,
  )


def run_command(cmd: str | Sequence[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
  """Run a command and log it."""
  if isinstance(cmd, str):
    args = shlex.split(cmd)
  else:
    args = list(cmd)

  log_args = args.copy()
  if log_args and log_args[0] == sys.executable:
    log_args[0] = "python"

  logger.info("$ %s", " ".join(shlex.quote(a) for a in log_args))
  return subprocess.run(args, check=check, **kwargs)


def check_command_exists(cmd: str) -> bool:
  """Return ``True`` if *cmd* exists in ``PATH``."""
  result = run_command(["which", cmd], check=False, capture_output=True, text=True)
  return result.returncode == 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
  """Add common arguments to *parser* (logging + working directory)."""
  parser.add_argument(
    "-v",
    "--verbose",
    action="count",
    default=0,
    help="Increase log verbosity (can be repeated)",
  )
  parser.add_argument("--log-file", help="Write logs to this file as well")
  parser.add_argument(
    "-C",
    "--directory",
    type=Path,
    help="Change to this directory before running",
  )


def add_logging_args(parser: argparse.ArgumentParser) -> None:
  """Add common logging arguments to *parser*.

  Deprecated: Use add_common_args() instead.
  """
  parser.add_argument(
    "-v",
    "--verbose",
    action="count",
    default=0,
    help="Increase log verbosity (can be repeated)",
  )
  parser.add_argument("--log-file", help="Write logs to this file as well")


@contextlib.contextmanager
def working_directory(path: Path | None) -> Generator[None, None, None]:
  """Context manager to temporarily change working directory."""
  if path is None:
    yield
    return

  original = Path.cwd()
  try:
    os.chdir(path)
    logger.debug("Changed to directory: %s", path)
    yield
  finally:
    os.chdir(original)


def find_project_root(start: Path | None = None) -> Path:
  """Find project root by looking for pyproject.toml."""
  current = Path.cwd() if start is None else start

  while current != current.parent:
    if (current / "pyproject.toml").exists():
      return current
    current = current.parent

  # If no pyproject.toml found, return original directory
  return Path.cwd() if start is None else start


def setup_working_directory(args: argparse.Namespace) -> contextlib.AbstractContextManager:
  """Setup working directory based on command arguments.

  If args.directory is specified, change to that directory.
  Otherwise, change to project root (directory containing pyproject.toml).
  """
  if hasattr(args, "directory") and args.directory:
    return working_directory(args.directory)
  else:
    # Default to project root
    project_root = find_project_root()
    if project_root != Path.cwd():
      logger.debug("Changing to project root: %s", project_root)
      return working_directory(project_root)
    else:
      # Already at project root, no-op context manager
      return contextlib.nullcontext()
