"""
Type definitions and protocols for the observability package.

Defines the core contracts and data structures used throughout the observability
system. These types enable static analysis while maintaining runtime flexibility.
"""

from typing import Any, Callable, Dict, List, Protocol, TypedDict, Union
from typing_extensions import NotRequired


class EventDict(TypedDict):
  """
  Structure of events flowing through the observability pipeline.

  Core fields are always present, while context and domain fields
  are optionally included based on the event source and active context.
  """

  # Core fields
  type: str  # Event type using dot notation (e.g., 'log.error')
  value: Any  # Primary event value
  timestamp_ns: int  # Nanoseconds since module initialization

  # Context fields (from contextvars)
  trace_id: NotRequired[str]
  request_id: NotRequired[str]
  operation_id: NotRequired[str]

  # Logging domain fields
  logger: NotRequired[str]
  level: NotRequired[int]
  template: NotRequired[str]
  args: NotRequired[tuple]

  # Tracing domain fields
  span_id: NotRequired[str]
  parent_id: NotRequired[str]
  duration_ns: NotRequired[int]
  success: NotRequired[bool]
  error: NotRequired[str]

  # Metrics domain fields
  measurement: NotRequired[Union[int, float]]
  help: NotRequired[str]
  buckets: NotRequired[tuple]
  delta: NotRequired[bool]

  # User-defined fields (kwargs from emit())
  # Any additional string keys are allowed


class EventHandler(Protocol):
  """Protocol defining the event handler interface."""

  def __call__(self, event: EventDict) -> None:
    """
    Process an event.

    Args:
        event: Event dictionary to process

    Note:
        Handlers must not raise exceptions. Any errors should be
        handled internally or logged to stderr.
    """
    ...


# Handler composition protocols
class HandlerFilter(Protocol):
  """Protocol for event filtering predicates."""

  def __call__(self, event: EventDict) -> bool:
    """
    Determine if an event should be processed.

    Args:
        event: Event to evaluate

    Returns:
        True if event should be processed, False to skip
    """
    ...


class HandlerTransform(Protocol):
  """Protocol for event transformation functions."""

  def __call__(self, event: EventDict) -> EventDict:
    """
    Transform an event before processing.

    Args:
        event: Original event

    Returns:
        Transformed event
    """
    ...


# Type aliases for clarity
HandlerFactory = Callable[..., EventHandler]
"""Function that creates and returns an event handler."""

HandlerList = List[EventHandler]
"""Collection of event handlers."""

CategorySet = set[str]
"""Set of event category names for filtering."""

ContextValue = Union[str, int, float, bool, None]
"""Valid types for context variable values."""

Labels = Dict[str, str]
"""Metric labels as string key-value pairs."""

CapturedEvents = List[EventDict]
"""List of events captured during testing."""


# Export all public types
__all__ = [
  # Core contracts
  "EventDict",
  "EventHandler",
  # Handler composition
  "HandlerFilter",
  "HandlerTransform",
  "HandlerFactory",
  # Common types
  "HandlerList",
  "CategorySet",
  "ContextValue",
  "Labels",
  "CapturedEvents",
]
