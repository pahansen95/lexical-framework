"""Helper tool framework.

Each tool registers a function that extends the command line interface
by adding a subparser. The :mod:`helpers.tools.__main__` entry point
builds the CLI by loading all modules and invoking these registration
callbacks.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Callable, Dict
import argparse

try:
  SubParser = argparse._SubParsersAction[argparse.ArgumentParser]
except TypeError:  # pragma: no cover - older Python
  # Python <3.11 doesn't allow subscripting _SubParsersAction
  SubParser = argparse._SubParsersAction  # type: ignore[type-arg]

TOOL_REGISTRY: Dict[str, Callable[[SubParser], None]] = {}


def register_tool(name: str, func: Callable[[SubParser], None]) -> None:
  """Register *func* to extend the CLI under ``name``."""

  TOOL_REGISTRY[name] = func


def tool(name: str) -> Callable[[Callable[[SubParser], None]], Callable[[SubParser], None]]:
  """Decorator to register *name* as a tool."""

  def decorator(func: Callable[[SubParser], None]) -> Callable[[SubParser], None]:
    register_tool(name, func)
    return func

  return decorator


def load_tools() -> None:
  """Import all tool modules so they can register themselves."""

  pkg_dir = Path(__file__).parent
  for module in pkgutil.iter_modules([str(pkg_dir)]):
    if module.name in {"__init__", "__main__"}:
      continue
    importlib.import_module(f"{__name__}.{module.name}")

