#!/usr/bin/env python3
"""Layer 2: Managed Tools - Install and configure uv, pyenv, and Python."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .state import BootstrapState
from .platform import get_platform_handler
from .verify import verify_tool
from ..utils import configure_logging, run_command, check_command_exists

logger = logging.getLogger(__name__)


def install_uv(platform_handler) -> dict[str, Any]:
  """Install uv using the provided *platform_handler*."""
  return platform_handler.install_uv()


def install_pyenv(platform_handler) -> dict[str, Any]:
  """Install pyenv using the provided *platform_handler*."""
  return platform_handler.install_pyenv()


def ensure_python_version(target_version: str) -> dict[str, Any]:
  """Ensure the target Python version is available."""
  result = {"python": {"version": target_version, "available": False, "installed": False, "error": None}}

  # Check if Python version is already available
  try:
    # Try direct python command
    for python_cmd in [f"python{target_version}", "python3", "python"]:
      if check_command_exists(python_cmd):
        version_check = run_command([python_cmd, "--version"], check=False)
        if version_check.returncode == 0 and target_version in version_check.stdout:
          result["python"]["available"] = True
          result["python"]["installed"] = True
          logger.info("Python %s already available via %s", target_version, python_cmd)
          return result

    # Try pyenv if available
    if check_command_exists("pyenv"):
      # Check installed versions
      versions_result = run_command(["pyenv", "versions", "--bare"], check=False)
      if versions_result.returncode == 0:
        installed_versions = versions_result.stdout.strip().split("\n")
        if target_version in installed_versions:
          result["python"]["available"] = True
          result["python"]["installed"] = True
          logger.info("Python %s available via pyenv", target_version)
          return result

      # Install via pyenv
      logger.info("Installing Python %s via pyenv...", target_version)
      install_result = run_command(["pyenv", "install", target_version], check=False)
      if install_result.returncode == 0:
        result["python"]["available"] = True
        result["python"]["installed"] = True
        logger.info("Python %s installed successfully", target_version)
      else:
        result["python"]["error"] = f"pyenv install failed: {install_result.stderr}"

    else:
      result["python"]["error"] = "pyenv not available for Python installation"

  except Exception as e:
    result["python"]["error"] = str(e)
    logger.error("Failed to ensure Python version: %s", e)

  return result


def get_project_python_version(project_root: Path) -> str | None:
  """Read Python version from .python-version file."""
  version_file = project_root / ".python-version"
  if version_file.exists():
    return version_file.read_text().strip()
  return None


def verify_uv() -> dict[str, Any]:
  """Verify uv installation."""
  return {"uv": verify_tool("uv")}


def verify_pyenv() -> dict[str, Any]:
  """Verify pyenv installation."""
  return {"pyenv": verify_tool("pyenv")}


def verify_python_version(version: str) -> dict[str, Any]:
  """Check if *version* of Python is available."""
  for cmd in [f"python{version}", "python3", "python"]:
    if check_command_exists(cmd):
      out = run_command([cmd, "--version"], check=False, capture_output=True, text=True)
      if out.returncode == 0 and version in out.stdout:
        return {"python": {"version": version, "available": True}}
  if check_command_exists("pyenv"):
    versions_result = run_command(["pyenv", "versions", "--bare"], check=False, capture_output=True, text=True)
    if versions_result.returncode == 0 and version in versions_result.stdout.splitlines():
      return {"python": {"version": version, "available": True}}
  return {"python": {"version": version, "available": False}}


def main() -> None:
  """Install and configure managed tools."""
  parser = argparse.ArgumentParser(description="Layer 2: Managed Tools")
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
  parser.add_argument("--skip-uv", action="store_true", help="Skip uv installation")
  parser.add_argument("--skip-pyenv", action="store_true", help="Skip pyenv installation")
  parser.add_argument("--skip-python", action="store_true", help="Skip Python installation")
  parser.add_argument("--python", help="Override Python version to install")
  args = parser.parse_args()

  configure_logging(args.verbose)

  # Read input state from stdin
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
  if state.platform is None:
    state.platform = get_platform_handler()
  project_root = Path(state.project_root)

  layer_results: dict[str, Any] = {}

  if not args.skip_uv:
    if verify_uv()["uv"]["installed"]:
      state.record_decision("uv", "reuse")
    else:
      uv_res = install_uv(state.platform)
      layer_results.update(uv_res)
      state.record_decision("uv", "install")
    uv_verify = verify_uv()
    state.record_verification("uv", uv_verify)
    if uv_verify["uv"]["installed"]:
      state.installed_tools["uv"] = uv_verify["uv"]

  # Install pyenv (optional, not critical)
  if not args.skip_pyenv:
    if verify_pyenv()["pyenv"]["installed"]:
      state.record_decision("pyenv", "reuse")
    else:
      pyenv_res = install_pyenv(state.platform)
      layer_results.update(pyenv_res)
      state.record_decision("pyenv", "install")
    pyenv_verify = verify_pyenv()
    state.record_verification("pyenv", pyenv_verify)
    if pyenv_verify["pyenv"]["installed"]:
      state.installed_tools["pyenv"] = pyenv_verify["pyenv"]

  # Ensure Python version
  if not args.skip_python:
    python_version = args.python or get_project_python_version(project_root) or "3.13"
    if verify_python_version(python_version)["python"]["available"]:
      state.record_decision("python", "reuse")
    else:
      py_res = ensure_python_version(python_version)
      layer_results.update(py_res)
      state.record_decision("python", "install")
    py_verify = verify_python_version(python_version)
    state.record_verification("python", py_verify)
    state.installed_tools["python"] = {"version": python_version, "installed": py_verify["python"]["available"]}

  if not args.skip_uv and not state.installed_tools.get("uv", {}).get("installed"):
    logger.error("Critical: uv installation failed")
    state.errors.append("uv installation failed")

  state.layer = 2
  state.layers.append({"layer": 2, "name": "managed_tools", "results": layer_results})

  json.dump(state.to_dict(), sys.stdout, indent=2)
  print()

  logger.info("Layer 2 configuration complete")


if __name__ == "__main__":
  main()
