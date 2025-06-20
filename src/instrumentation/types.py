"""Type definitions for the instrumentation framework."""

from typing import Protocol, TypedDict, Any, Dict
from typing_extensions import NotRequired


class EventDict(TypedDict):
  """Structure of instrumentation events."""

  type: str
  value: Any
  timestamp_ms: float
  # Optional context fields
  trace_id: NotRequired[str]
  depth: NotRequired[int]
  rule: NotRequired[str]
  file: NotRequired[str]
  error: NotRequired[str]
  success: NotRequired[bool]


class EventHandler(Protocol):
  """Protocol for event handlers."""

  def __call__(self, event: EventDict) -> None: ...


class MetricsDict(TypedDict):
  """Structure returned by metrics handlers."""

  counters: Dict[str, int]
  durations: Dict[str, Dict[str, float]]
  values: Dict[str, Dict[str, float]]
