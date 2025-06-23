"""
Base handler types and shared utilities.

Provides foundational protocols and utilities used across handler implementations.
This module defines contracts for managed handlers and common helper functions
that ensure consistent behavior across the handler ecosystem.
"""

import sys
from typing import Any, Protocol, runtime_checkable
from ..types import EventDict


@runtime_checkable
class LifecycleHandler(Protocol):
  """Handler with async lifecycle management."""

  async def initialize(self) -> None:
    """Initialize handler resources."""
    ...

  async def shutdown(self) -> None:
    """Shutdown handler and release resources."""
    ...


@runtime_checkable
class ManagedHandler(Protocol):
  """Handler with synchronous resource management."""

  def close(self) -> None:
    """Release handler resources gracefully."""
    ...

  def flush(self) -> None:
    """Force pending operations to complete."""
    ...


# Common formatting utilities
def format_event_simple(event: EventDict, template: str) -> str:
  """
  Format event using simple template substitution.

  Args:
      event: Event dictionary to format
      template: Format string with {field} placeholders

  Returns:
      Formatted string
  """
  # Prepare format dict with computed fields
  fmt_dict = event.copy()
  fmt_dict["timestamp_ms"] = event["timestamp_ns"] / 1_000_000

  try:
    return template.format(**fmt_dict)
  except (KeyError, ValueError) as e:
    # Fallback for format errors
    return f"Format error: {template!r} - {e}"


def format_context_items(event: EventDict, exclude: set[str]) -> list[str]:
  """
  Extract context items from event for display.

  Args:
      event: Event dictionary
      exclude: Fields to exclude from context

  Returns:
      List of "key=value" strings
  """
  context_items = []
  for key, value in event.items():
    if key not in exclude:
      context_items.append(f"{key}={value}")
  return context_items


def safe_handler_call(handler_name: str, operation: str, error: Exception) -> None:
  """
  Report handler errors safely in debug mode.

  Args:
      handler_name: Name of the handler that failed
      operation: What operation failed
      error: The exception that occurred
  """
  if __debug__:
    print(f"{handler_name} {operation} error: {error}", file=sys.stderr)


# Event field sets for common exclusions
CORE_EVENT_FIELDS = {"type", "value", "timestamp_ns"}
STANDARD_EXCLUSIONS = CORE_EVENT_FIELDS | {"timestamp_ms"}


# Handler naming utilities
def get_handler_name(handler: Any) -> str:
  """
  Get a readable name for a handler.

  Args:
      handler: Handler instance or function

  Returns:
      Handler name or representation
  """
  return getattr(handler, "__name__", repr(handler))


def set_handler_name(handler: Any, name: str) -> None:
  """
  Set a handler's name for debugging.

  Args:
      handler: Handler to name
      name: Name to assign
  """
  try:
    handler.__name__ = name
  except AttributeError:
    pass  # Some objects don't allow name assignment
