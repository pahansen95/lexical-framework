from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from helpers.bootstrap.platform import Platform

import logging

"""Structured state object for the bootstrap helper."""

logger = logging.getLogger(__name__)


@dataclass
class BootstrapState:
  """State passed between bootstrap layers."""

  project_root: str
  platform: Optional[Platform] = None
  layer: int = 0
  layers: List[Dict[str, Any]] = field(default_factory=list)

  available_tools: Dict[str, Any] = field(default_factory=dict)
  installed_tools: Dict[str, Any] = field(default_factory=dict)
  tools: Dict[str, Dict[str, Any]] = field(default_factory=dict)

  warnings: List[str] = field(default_factory=list)
  errors: List[str] = field(default_factory=list)
  decisions: Dict[str, str] = field(default_factory=dict)
  verifications: Dict[str, Any] = field(default_factory=dict)

  @classmethod
  def from_dict(cls, data: Dict[str, Any]) -> "BootstrapState":
    """Create state from dictionary representation."""
    # Extract platform name if present
    platform_name = data.pop("platform", None)

    # Create state instance
    state = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    # Recreate platform object if needed
    if platform_name and not state.platform:
      from helpers.bootstrap.platform import get_platform_handler

      state.platform = get_platform_handler()

    return state

  def to_dict(self) -> Dict[str, Any]:
    """Convert state to a JSON serialisable dictionary."""
    data = asdict(self)
    # Convert platform to string representation
    if self.platform:
      data["platform"] = self.platform.name
    return data

  def can_proceed(self) -> bool:
    """Return ``True`` if the bootstrap process should continue."""
    return len(self.errors) == 0

  def record_decision(self, component: str, decision: str) -> None:
    """Record an installation or configuration decision."""
    self.decisions[component] = decision
    logger.debug("Decision recorded: %s -> %s", component, decision)

  def record_verification(self, component: str, result: Dict[str, Any]) -> None:
    """Store verification *result* for *component*."""
    self.verifications[component] = result
    logger.debug("Verification recorded: %s -> %s", component, result)
