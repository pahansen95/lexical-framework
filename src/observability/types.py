"""
# Type Definitions and Protocols

Type contracts and data structures that define the observability system's communication protocol. These types establish the boundaries between event producers, the transport layer, and event consumers while enabling static analysis and runtime flexibility.

## Data Flow Model

The type system defines how information flows through the observability pipeline:

```
Domain Layer          Transport Layer         Handler Layer
(Producers)           (EventDict)            (Consumers)

Logger ─────┐
            ├─→ EventDict ─→ Handler Protocol ─→ File
Tracer ─────┤                                  ─→ Network
            ├─→ Immutable ─→ Type-Safe       ─→ Memory
Counter ────┘   Structure    Interface
```

EventDict serves as the universal message format - a structured record that carries all event data through the system. Its design balances static type safety with dynamic extensibility.

## Core Contracts

**EventDict**: The fundamental message structure flowing through the system
- Core fields present in every event (type, value, timestamp)
- Optional context fields from ambient environment
- Domain-specific fields based on event source
- User-defined metadata for extensibility

**EventHandler Protocol**: The consumer interface contract
- Single method accepting EventDict
- No return value (pure side effect)
- Error isolation requirement
- Composability guarantee

## Type Architecture

The type system implements a layered approach:

1. **Base Layer**: Core fields required by all events
2. **Context Layer**: Ambient data from contextvars
3. **Domain Layer**: Specialized fields per observability domain
4. **Extension Layer**: Arbitrary user-defined metadata

This architecture enables:
- Type checking for known fields
- Runtime flexibility for custom data
- Clear contracts between components
- Static analysis of handler compatibility

## Protocol Definitions

**Handler Composition Protocols**: Building blocks for complex handlers
- `HandlerFilter`: Predicates controlling event flow
- `HandlerTransform`: Event modification functions
- `HandlerFactory`: Functions creating configured handlers

These protocols enable type-safe handler composition while maintaining the simplicity of the base EventHandler interface.

## Type Aliases

Semantic type aliases improve code clarity:

```python
HandlerList = List[EventHandler]      # Multiple handlers
CategorySet = set[str]                # Event filtering
Labels = Dict[str, str]               # Metric dimensions
ContextValue = Union[str, int, ...]   # Valid context types
```

## Design Principles

- **Structural Typing**: Use protocols over inheritance for flexibility
- **Gradual Enhancement**: Core types are simple, complexity is opt-in
- **Immutability**: EventDict represents a snapshot, never modified
- **Extensibility**: Unknown fields are preserved, not rejected

## Type Safety Patterns

The type system enables several safety patterns:

1. **Compile-Time Validation**: Known fields checked statically
2. **Runtime Flexibility**: Extra fields allowed dynamically
3. **Protocol Compliance**: Handlers verified at boundaries
4. **Context Preservation**: Type information flows with data

This design ensures that:
- Domain code gets IDE support and type checking
- Handlers can process any event generically
- New domains can be added without modifying core types
- Static analysis tools can verify correctness

The type system forms the contract that enables independent evolution of event producers and consumers while maintaining compatibility and safety.
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
