"""Manage Python versions and virtual environments."""

from __future__ import annotations

import argparse
from pathlib import Path

from helpers.utils import logger, run_command
from helpers.tools import tool, SubParser

VENV_WANT = "dev"

BASE_VENV_DIR = Path(".venv")


def resolve_venv_path(name: str) -> Path:
  """Return path for virtual environment *name*."""
  return BASE_VENV_DIR if name == "default" else BASE_VENV_DIR / name


def ensure_venv_exists(name: str) -> Path:
  """Return path to existing virtual environment *name*, or exit."""
  path = resolve_venv_path(name)
  if not path.exists():
    logger.error("Virtual environment '%s' not found", name)
    raise SystemExit(1)
  return path


def install_python(args: argparse.Namespace) -> None:
  """Install Python version from .python-version file."""
  version_file = Path(".python-version")
  if not version_file.exists():
    logger.error(".python-version file not found")
    raise SystemExit(1)

  version = version_file.read_text().strip()
  logger.debug("target version: %s", version)

  result = run_command([
    "pyenv",
    "versions",
    "--bare",
  ], capture_output=True, text=True, check=False)

  installed = result.stdout.strip().split("\n") if result.stdout else []
  if version in installed and not args.force:
    logger.info("Python %s is already installed", version)
    return

  logger.info("Installing Python %s...", version)
  run_command(["pyenv", "install", version] + (["--force"] if args.force else []))
  logger.info("Python %s installed successfully", version)


def create_venv(args: argparse.Namespace) -> None:
  """Create a named virtual environment with optional parent symlink."""
  venv_path = resolve_venv_path(args.name)

  if args.symlink_parent and BASE_VENV_DIR.exists() and not BASE_VENV_DIR.is_symlink():
    logger.error("Cannot create parent symlink: %s already exists", BASE_VENV_DIR)
    raise SystemExit(1)

  if args.symlink_parent and not BASE_VENV_DIR.exists():
    target = Path(args.symlink_parent).expanduser().resolve()
    if not target.exists():
      logger.info("Creating parent venv directory at %s", target)
      target.mkdir(parents=True, mode=0o755)

    logger.info("Symlinking %s -> %s", BASE_VENV_DIR, target)
    BASE_VENV_DIR.symlink_to(target)

  if venv_path.exists() and not args.force:
    logger.info("Virtual environment '%s' already exists", args.name)
    return

  logger.info("Creating virtual environment '%s'...", args.name)
  cmd = ["uv", "venv", str(venv_path)]
  if args.force:
    cmd.append("--force")
  run_command(cmd)
  logger.info("Virtual environment '%s' created at %s", args.name, venv_path)


def list_venvs(args: argparse.Namespace) -> None:
  """List all virtual environments."""
  if not BASE_VENV_DIR.exists():
    logger.info("No virtual environments found")
    return

  if BASE_VENV_DIR.is_symlink():
    target = BASE_VENV_DIR.resolve()
    print(f"Venv parent: {BASE_VENV_DIR} -> {target}")
  else:
    print(f"Venv parent: {BASE_VENV_DIR}")

  if BASE_VENV_DIR.is_dir():
    venvs: list[str] = []
    if (BASE_VENV_DIR / "pyvenv.cfg").exists():
      venvs.append("default")
    else:
      for d in sorted(BASE_VENV_DIR.iterdir()):
        if d.is_dir() and (d / "pyvenv.cfg").exists():
          venvs.append(d.name)

    if venvs:
      print("\nAvailable virtual environments:")
      for venv in venvs:
        print(f"  - {venv}")


def install_deps(args: argparse.Namespace) -> None:
  """Install dependency group in virtual environment."""
  venv_path = ensure_venv_exists(args.venv)

  logger.info("Installing '%s' dependencies in '%s'...", args.group, args.venv)

  if args.group == "base":
    cmd = ["uv", "pip", "install", "-r", "uv.lock"]
  else:
    cmd = ["uv", "pip", "install", "--group", args.group]

  cmd.extend(["--python", str(venv_path)])

  run_command(cmd)
  logger.info("Dependencies installed successfully")


def run_in_venv(args: argparse.Namespace) -> None:
  """Run command in virtual environment."""
  venv_path = ensure_venv_exists(args.venv)

  logger.debug("Running in venv '%s': %s", args.venv, args.command)

  cmd = ["uv", "run", "--python", str(venv_path), *args.command]
  run_command(cmd)


@tool("python")
def register(subparsers: SubParser) -> None:
  parser = subparsers.add_parser("python", help="Manage Python versions and virtualenvs")
  actions = parser.add_subparsers(dest="action", required=True)

  install_parser = actions.add_parser("install", help="Install Python version")
  install_parser.add_argument("--force", action="store_true", help="Force reinstall even if version exists")
  install_parser.set_defaults(func=install_python)

  venv_parser = actions.add_parser("venv", help="Create virtual environment")
  venv_parser.add_argument("name", default="default", nargs="?", help="Virtual environment name (default: 'default')")
  venv_parser.add_argument("--force", action="store_true", help="Recreate if exists")
  venv_parser.add_argument("--symlink-parent", metavar="PATH", help="Create parent .venv as symlink to PATH")
  venv_parser.set_defaults(func=create_venv)

  list_parser = actions.add_parser("list", help="List virtual environments")
  list_parser.set_defaults(func=list_venvs)

  deps_parser = actions.add_parser("deps", help="Install dependency group")
  deps_parser.add_argument(
    "group",
    choices=["base", "dev", "build", "docs", "test"],
    help="Dependency group to install",
  )
  deps_parser.add_argument("--venv", default="default", help="Virtual environment name (default: 'default')")
  deps_parser.set_defaults(func=install_deps)

  run_parser = actions.add_parser("run", help="Run command in venv")
  run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")
  run_parser.add_argument("--venv", default="default", help="Virtual environment name (default: 'default')")
  run_parser.set_defaults(func=run_in_venv)

