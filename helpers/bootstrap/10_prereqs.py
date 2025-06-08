#!/usr/bin/env python3
"""Layer 1: Prerequisites - Probe development tools and prerequisites."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from helpers.bootstrap.state import BootstrapState

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
  """Configure logging to stderr."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
    level=level,
    format="[L1] %(levelname)s: %(message)s",
    stream=sys.stderr,
  )


def run_command(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
  """Run command and return (returncode, stdout, stderr)."""
  try:
    result = subprocess.run(
      cmd,
      capture_output=True,
      text=True,
      timeout=timeout,
      env={**os.environ, "LC_ALL": "C"},  # Ensure consistent output
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()
  except subprocess.TimeoutExpired:
    return -1, "", "Command timed out"
  except FileNotFoundError:
    return -1, "", "Command not found"
  except Exception as e:
    return -1, "", str(e)


def probe_shell_environment() -> dict[str, Any]:
  """Probe shell environment and capabilities."""
  result = {
    "current_shell": None,
    "available_shells": [],
    "shell_version": None,
    "is_interactive": sys.stdin.isatty(),
    "terminal": os.environ.get("TERM"),
    "color_support": False,
  }

  # Current shell
  shell_env = os.environ.get("SHELL")
  if shell_env:
    result["current_shell"] = shell_env
    shell_name = Path(shell_env).name

    # Get shell version
    if shell_name in ["bash", "zsh", "fish"]:
      code, stdout, _ = run_command([shell_env, "--version"])
      if code == 0 and stdout:
        result["shell_version"] = stdout.split("\n")[0]

  # Available shells
  shells_to_check = ["bash", "zsh", "fish", "sh", "dash"]
  for shell in shells_to_check:
    code, stdout, _ = run_command(["which", shell])
    if code == 0 and stdout:
      result["available_shells"].append(
        {
          "name": shell,
          "path": stdout,
        }
      )

  # Color support
  if result["terminal"] and "color" in result["terminal"].lower():
    result["color_support"] = True
  elif os.environ.get("COLORTERM"):
    result["color_support"] = True

  return result


def probe_git_installation() -> dict[str, Any]:
  """Probe git installation and configuration."""
  result = {
    "installed": False,
    "version": None,
    "path": None,
    "config": {},
    "features": {},
  }

  # Check if git is installed
  code, stdout, _ = run_command(["which", "git"])
  if code == 0 and stdout:
    result["installed"] = True
    result["path"] = stdout

    # Get version
    code, stdout, _ = run_command(["git", "--version"])
    if code == 0:
      match = re.search(r"git version ([\d.]+)", stdout)
      if match:
        result["version"] = match.group(1)

    # Get basic config
    config_items = [
      ("user.name", "user_name"),
      ("user.email", "user_email"),
      ("core.editor", "editor"),
      ("init.defaultBranch", "default_branch"),
    ]

    for git_key, result_key in config_items:
      code, stdout, _ = run_command(["git", "config", "--global", git_key])
      if code == 0 and stdout:
        result["config"][result_key] = stdout

    # Check for common features
    code, _, _ = run_command(["git", "lfs", "version"])
    result["features"]["lfs"] = code == 0

    # Check if we're in a git repository
    code, stdout, _ = run_command(["git", "rev-parse", "--git-dir"])
    result["in_repository"] = code == 0

  return result


def probe_python_installations() -> dict[str, Any]:
  """Probe all Python installations on the system."""
  result = {
    "current": {
      "version": sys.version,
      "executable": sys.executable,
      "prefix": sys.prefix,
      "implementation": sys.implementation.name,
    },
    "available_pythons": [],
    "pip_installed": False,
    "venv_module": False,
  }

  # Check for pip
  code, stdout, _ = run_command([sys.executable, "-m", "pip", "--version"])
  if code == 0:
    result["pip_installed"] = True
    result["pip_version"] = stdout.split()[1] if stdout else None

  # Check for venv module
  code, _, _ = run_command([sys.executable, "-m", "venv", "--help"], timeout=2)
  result["venv_module"] = code == 0

  # Find other Python installations
  python_commands = [
    "python",
    "python3",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
    "python3.9",
    "python3.8",
  ]

  found_pythons = {}
  for cmd in python_commands:
    code, stdout, _ = run_command(["which", cmd])
    if code == 0 and stdout:
      # Get version
      code, version_out, _ = run_command([stdout, "--version"])
      if code == 0:
        match = re.search(r"Python ([\d.]+)", version_out)
        if match:
          version = match.group(1)
          # Deduplicate by executable path
          real_path = Path(stdout).resolve()
          if str(real_path) not in found_pythons:
            found_pythons[str(real_path)] = {
              "command": cmd,
              "path": stdout,
              "version": version,
              "real_path": str(real_path),
            }

  result["available_pythons"] = list(found_pythons.values())

  return result


def probe_package_managers() -> dict[str, Any]:
  """Probe available package managers."""
  result = {
    "system": {},
    "python": {},
    "language": {},
  }

  # System package managers
  system_pms = {
    "apt": ["apt", "--version"],
    "yum": ["yum", "--version"],
    "dnf": ["dnf", "--version"],
    "pacman": ["pacman", "--version"],
    "brew": ["brew", "--version"],
    "port": ["port", "version"],
    "choco": ["choco", "--version"],
    "scoop": ["scoop", "--version"],
  }

  for name, cmd in system_pms.items():
    code, stdout, _ = run_command(cmd)
    if code == 0:
      result["system"][name] = {
        "installed": True,
        "version": stdout.split("\n")[0] if stdout else "unknown",
      }

  # Python package managers
  python_pms = {
    "pip": [sys.executable, "-m", "pip", "--version"],
    "pipx": ["pipx", "--version"],
    "poetry": ["poetry", "--version"],
    "pdm": ["pdm", "--version"],
    "uv": ["uv", "--version"],
    "conda": ["conda", "--version"],
    "mamba": ["mamba", "--version"],
  }

  for name, cmd in python_pms.items():
    code, stdout, _ = run_command(cmd)
    if code == 0:
      result["python"][name] = {
        "installed": True,
        "version": stdout.strip(),
      }

  # Other language package managers (for context)
  other_pms = {
    "npm": ["npm", "--version"],
    "yarn": ["yarn", "--version"],
    "cargo": ["cargo", "--version"],
    "go": ["go", "version"],
  }

  for name, cmd in other_pms.items():
    code, stdout, _ = run_command(cmd)
    if code == 0:
      result["language"][name] = {
        "installed": True,
        "version": stdout.strip(),
      }

  return result


def probe_development_tools() -> dict[str, Any]:
  """Probe common development tools."""
  result = {
    "editors": {},
    "tools": {},
    "version_managers": {},
  }

  # Text editors/IDEs
  editors = {
    "vim": ["vim", "--version"],
    "nvim": ["nvim", "--version"],
    "emacs": ["emacs", "--version"],
    "code": ["code", "--version"],
    "subl": ["subl", "--version"],
    "atom": ["atom", "--version"],
  }

  for name, cmd in editors.items():
    code, stdout, _ = run_command(cmd)
    if code == 0:
      result["editors"][name] = True

  # Development tools
  tools = {
    "make": ["make", "--version"],
    "gcc": ["gcc", "--version"],
    "clang": ["clang", "--version"],
    "docker": ["docker", "--version"],
    "curl": ["curl", "--version"],
    "wget": ["wget", "--version"],
    "jq": ["jq", "--version"],
  }

  for name, cmd in tools.items():
    code, stdout, _ = run_command(cmd)
    if code == 0:
      result["tools"][name] = {
        "installed": True,
        "version": stdout.split("\n")[0] if stdout else "unknown",
      }

  # Version managers
  version_managers = {
    "pyenv": ["pyenv", "--version"],
    "rbenv": ["rbenv", "--version"],
    "nvm": ["nvm", "--version"],
    "asdf": ["asdf", "--version"],
  }

  for name, cmd in version_managers.items():
    # Some version managers are shell functions, try different approaches
    if name == "nvm":
      # nvm is typically a shell function
      nvm_dir = os.environ.get("NVM_DIR")
      if nvm_dir and Path(nvm_dir).exists():
        result["version_managers"][name] = {"installed": True, "path": nvm_dir}
    else:
      code, stdout, _ = run_command(cmd)
      if code == 0:
        result["version_managers"][name] = {
          "installed": True,
          "version": stdout.strip(),
        }

  return result


def check_prerequisites() -> dict[str, bool]:
  """Check if minimum prerequisites are met."""
  checks = {}

  # Essential checks
  code, _, _ = run_command(["which", "git"])
  checks["git_available"] = code == 0

  # Python 3.7+ (for subprocess.run capture_output parameter)
  checks["python_version_ok"] = sys.version_info >= (3, 7)

  # Can create virtual environments
  code, _, _ = run_command([sys.executable, "-m", "venv", "--help"], timeout=2)
  checks["venv_available"] = code == 0

  # Network utilities
  code, _, _ = run_command(["which", "curl"])
  curl_available = code == 0
  code, _, _ = run_command(["which", "wget"])
  wget_available = code == 0
  checks["download_tool_available"] = curl_available or wget_available

  return checks


def verify_prerequisites() -> dict[str, Any]:
  """Verify prerequisite availability."""
  return {"checks": check_prerequisites()}


def run(state: BootstrapState, *, quick: bool = False) -> BootstrapState:
  """Execute the prerequisites layer."""

  layer_results = {
    "shell": probe_shell_environment(),
    "git": probe_git_installation(),
    "python": probe_python_installations(),
  }

  if not quick:
    layer_results["package_managers"] = probe_package_managers()
    layer_results["dev_tools"] = probe_development_tools()

  prerequisite_checks = check_prerequisites()
  state.prerequisites_met = all(prerequisite_checks.values())
  state.prerequisite_checks = prerequisite_checks
  state.record_verification("prerequisites", verify_prerequisites())

  state.layer = 1
  state.layers.append({"layer": 1, "name": "prerequisites", "results": layer_results})

  return state


def main() -> None:
  """Probe prerequisites layer information."""
  parser = argparse.ArgumentParser(description="Layer 1: Prerequisites Probe")
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
  parser.add_argument("--quick", action="store_true", help="Skip slow probes")
  args = parser.parse_args()

  setup_logging(args.verbose)
  logger.info("Starting prerequisites layer probe")

  # Read input state from stdin (if any)
  if not sys.stdin.isatty():
    try:
      input_state = json.load(sys.stdin)
      logger.debug("Received input state: %s", input_state)
    except json.JSONDecodeError:
      logger.warning("Failed to parse input JSON, using defaults")
      input_state = {}
  else:
    input_state = {}

  if "project_root" not in input_state:
    input_state["project_root"] = str(Path.cwd())

  state = BootstrapState.from_dict(input_state)
  state = run(state, quick=args.quick)

  # Output state to stdout
  json.dump(state.to_dict(), sys.stdout, indent=2)
  print()  # Newline for readability

  if state.prerequisites_met:
    logger.info("Prerequisites layer probe complete - all requirements met")
  else:
    logger.warning("Prerequisites layer probe complete - missing requirements")
    for check, passed in state.prerequisite_checks.items():
      if not passed:
        logger.warning(f"  Missing: {check}")


if __name__ == "__main__":
  main()
