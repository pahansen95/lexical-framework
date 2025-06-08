"""Bootstrap module for layered environment setup."""

from __future__ import annotations

from .state import BootstrapState
from .platform import Platform, get_platform_handler

__version__ = "1.0.0"

# Layer definitions
LAYERS = {
  0: "Foundation (OS, architecture, network)",
  1: "Prerequisites (shell, git, base Python)",
  2: "Managed Tools (uv, pyenv, Python)",
  3: "Project Environment (venv, dependencies)",
  4: "Developer Experience (git hooks, IDE)",
}

__all__ = ["LAYERS", "__version__", "BootstrapState", "Platform", "get_platform_handler"]
