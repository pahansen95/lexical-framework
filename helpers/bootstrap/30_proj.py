#!/usr/bin/env python3
"""Layer 3: Project Environment - Setup virtual environment and install dependencies."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
import shutil
from typing import Any

from .state import BootstrapState
from .verify import verify_venv, verify_tool
from ..tools import python as pytools
from ..utils import configure_logging, run_command

logger = logging.getLogger(__name__)


def create_virtual_environment(project_root: Path, name: str, python_version: str | None = None) -> dict[str, Any]:
  """Create virtual environment *name* using uv."""
  result = {name: {"created": False, "path": None, "error": None}}

  target = "default" if name == "dev" else name
  venv_path = project_root / pytools.resolve_venv_path(target)

  try:
    if venv_path.exists():
      verification = verify_venv(venv_path)
      if verification["valid"]:
        logger.info("Valid virtual environment exists at %s", venv_path)
        result[name]["created"] = True
        result[name]["path"] = str(venv_path)
        return result
      if verification["corrupt"]:
        logger.warning("Invalid venv detected, recreating...")
        shutil.rmtree(venv_path)

    args = argparse.Namespace(
      name=target,
      force=False,
      symlink_parent=None,
      directory=project_root,
      verbose=0,
      log_file=None,
    )
    pytools.create_venv(args)
    result[name]["created"] = True
    result[name]["path"] = str(venv_path)
    logger.info("Created virtual environment at %s", venv_path)

  except subprocess.CalledProcessError as e:
    result[name]["error"] = f"Failed to create venv: {e}"
    logger.error("Virtual environment creation failed: %s", e)

  return result


def install_dependencies(project_root: Path, name: str, groups: list[str]) -> dict[str, Any]:
  """Install dependency *groups* in virtual environment *name*."""
  result = {"dependencies": {name: {}}}

  # Install each dependency group
  for group in groups:
    group_result = {"installed": False, "error": None}
    try:
      args = argparse.Namespace(
        group=group,
        venv="default" if name == "dev" else name,
        directory=project_root,
        verbose=0,
        log_file=None,
      )
      pytools.install_deps(args)
      group_result["installed"] = True
      logger.info("Installed '%s' in %s", group, name)
    except subprocess.CalledProcessError as e:
      logger.debug("Failed to install %s in %s: %s", group, name, e)
      group_result["error"] = str(e)

    result["dependencies"][name][group] = group_result

  return result


def install_development_tools(venv_path: Path) -> dict[str, Any]:
  """Install essential development tools in the virtual environment."""
  result = {"dev_tools": {"pre_commit": False, "mkdocs": False}}

  tools = [
    ("pre-commit", "pre_commit"),
    ("mkdocs", "mkdocs"),
  ]

  for package, result_key in tools:
    try:
      cmd = ["uv", "pip", "install", package, "--python", str(venv_path)]
      run_command(cmd, check=True)
      result["dev_tools"][result_key] = True
      logger.info("Installed %s", package)
    except subprocess.CalledProcessError:
      logger.debug("Failed to install %s (may already be in dependencies)", package)

  return result


def verify_project_structure(project_root: Path) -> dict[str, Any]:
  """Verify essential project files exist."""
  result = {"project_files": {"present": [], "missing": []}}

  essential_files = [
    "pyproject.toml",
    "README.md",
    ".gitignore",
  ]

  for file_name in essential_files:
    file_path = project_root / file_name
    if file_path.exists():
      result["project_files"]["present"].append(file_name)
    else:
      result["project_files"]["missing"].append(file_name)

  if result["project_files"]["missing"]:
    logger.warning("Missing project files: %s", ", ".join(result["project_files"]["missing"]))

  return result


def verify_dev_tools(venv_path: Path) -> dict[str, Any]:
  """Verify that development tools are available."""
  return {
    "dev_tools": {"pre_commit": verify_tool("pre-commit")["installed"], "mkdocs": verify_tool("mkdocs")["installed"]}
  }


def verify_dependencies_accessible(name: str, venv_path: Path) -> dict[str, Any]:
  """Check that pip is functional inside the venv."""
  res = run_command(["uv", "pip", "list", "--python", str(venv_path)], check=False)
  return {"dependencies": {name: {"accessible": res.returncode == 0}}}


def main() -> None:
  """Setup project environment."""
  parser = argparse.ArgumentParser(description="Layer 3: Project Environment")
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
  parser.add_argument("--python", help="Python version to use for venv")
  parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
  parser.add_argument("--skip-tools", action="store_true", help="Skip dev tool installation")
  args = parser.parse_args()

  configure_logging(args.verbose)

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
  project_root = Path(state.project_root)
  python_version = args.python or state.installed_tools.get("python", {}).get("version")

  if not project_root.exists():
    logger.error("Project root does not exist: %s", project_root)
    sys.exit(1)

  layer_results: dict[str, Any] = {}

  layer_results.update(verify_project_structure(project_root))

  venv_configs = {
    "dev": {"groups": ["base", "dev", "build", "docs"], "tools": True},
    "test": {"groups": ["base", "dev"], "tools": False},
    "docs": {"groups": ["base", "docs"], "tools": False},
  }

  for name, cfg in venv_configs.items():
    target = project_root / pytools.resolve_venv_path("default" if name == "dev" else name)
    initial = verify_venv(target)
    state.record_verification(f"venv_{name}", initial)
    if initial["valid"]:
      state.record_decision(f"venv_{name}", "reuse")
    else:
      venv_res = create_virtual_environment(project_root, name, python_version)
      layer_results.setdefault("venvs", {}).update(venv_res)
      state.record_decision(f"venv_{name}", "create" if venv_res[name]["created"] else "fail")
      state.record_verification(f"venv_{name}", verify_venv(target))

    if (target / "bin/python").exists():
      if not args.skip_deps:
        dep_res = install_dependencies(project_root, name, cfg["groups"])
        layer_results.setdefault("dependencies", {}).update(dep_res["dependencies"])
        dep_verify = verify_dependencies_accessible(name, target)
        state.record_verification(f"deps_{name}", dep_verify)

      if cfg["tools"] and not args.skip_tools:
        tools_res = install_development_tools(target)
        layer_results.setdefault("dev_tools", {}).update(tools_res["dev_tools"])
        state.record_decision(f"dev_tools_{name}", "install")
        state.record_verification(f"dev_tools_{name}", verify_dev_tools(target))
      elif cfg["tools"]:
        state.record_decision(f"dev_tools_{name}", "skip")

  # Pass through previous layer data
  state.layer = 3
  state.layers.append({"layer": 3, "name": "project_environment", "results": layer_results})

  # Output state to stdout
  json.dump(state.to_dict(), sys.stdout, indent=2)
  print()

  logger.info("Layer 3 configuration complete")


if __name__ == "__main__":
  main()
