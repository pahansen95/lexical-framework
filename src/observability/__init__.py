"""
# Observability Package

A unified event emission infrastructure that provides zero-overhead instrumentation for logging, tracing, and metrics collection. The package implements a tree-based event dispatch system where telemetry data flows through a central pipeline to multiple, independent handlers.

## Architecture

The observability system separates event production from consumption through a publish-subscribe model:

```
Application Code
    ↓ emit()
Core Event System
    ↓ dispatch
Handler Tree
    ├─→ Logging Handler → File/Console
    ├─→ Metrics Handler → Aggregation/Export
    └─→ Trace Handler   → Span Collection
```

This separation enables flexible telemetry collection where the same event can be processed differently by multiple handlers without coupling the event source to specific destinations.

## Core Concepts

**Events**: Immutable records containing typed data, timestamps, and contextual metadata that flow through the system.

**Domains**: Specialized APIs (logging, tracing, metrics) that translate high-level operations into structured events.

**Handlers**: Event consumers organized in a tree structure that process events independently with isolated error handling.

**Zero-Overhead**: When no handlers are attached, the entire system reduces to a single boolean check, ensuring production code pays no performance penalty for unused instrumentation.

## Design Principles

- **Unified Pipeline**: All telemetry flows through one event system
- **Domain Separation**: Each observability concern has its own intuitive API
- **Handler Composition**: Complex processing built from simple, focused handlers
- **Fail-Safe Operation**: Handler errors never affect event emission or other handlers
- **Context Propagation**: Automatic correlation through ambient context variables

## Basic Usage

```python
from observability import attach, logging, tracing, metrics

# Attach handlers to process events
attach(create_file_handler('app.log'))
attach(create_metrics_aggregator())

# Use domain APIs to emit events
logger = logging.get_logger('myapp')
logger.info('Application started')

with tracing.span('process_request'):
    metrics.Counter('requests').increment()
```

The package provides a foundation for comprehensive observability while maintaining simplicity and performance in production systems.
"""

from typing import Any

# Core event system
from .core import (
  # Event emission
  emit,
  # Handler management
  attach,
  detach,
  clear,
  # Performance utilities
  has_handlers,
  get_handler_count,
  # Context management
  set_context,
  # Category filtering
  enable_categories,
  disable_categories,
  reset_filters,
  # Testing support
  capture_events,
)

# Handler utilities
from .handlers import (
  # Basic handlers
  create_print_handler,
  create_file_handler,
  create_buffer_handler,
  # Composition handlers
  create_async_handler,
  create_conditional_handler,
  create_sampling_handler,
)

# Type exports for static analysis
from .types import EventDict, EventHandler


class _DomainNamespace:
  """Lazy-loading namespace for domain modules."""

  __slots__ = ("_module_name", "_module", "_loaded_attrs")

  def __init__(self, module_name: str):
    self._module_name = module_name
    self._module = None
    self._loaded_attrs = {}

  def __getattr__(self, name: str) -> Any:
    # Cache individual attributes to avoid repeated lookups
    if name in self._loaded_attrs:
      return self._loaded_attrs[name]

    # Lazy import on first access
    if self._module is None:
      import importlib

      self._module = importlib.import_module(self._module_name)

    attr = getattr(self._module, name)
    self._loaded_attrs[name] = attr
    return attr

  def __dir__(self):
    # Enable IDE autocompletion
    if self._module is None:
      import importlib

      self._module = importlib.import_module(self._module_name)
    return dir(self._module)


# Domain namespaces
logging = _DomainNamespace("observability.domains.logging")
tracing = _DomainNamespace("observability.domains.tracing")
metrics = _DomainNamespace("observability.domains.metrics")

# Public API
__all__ = [
  # Core functions
  "emit",
  "attach",
  "detach",
  "clear",
  "has_handlers",
  "get_handler_count",
  "set_context",
  "capture_events",
  "enable_categories",
  "disable_categories",
  "reset_filters",
  # Handler factories
  "create_print_handler",
  "create_file_handler",
  "create_buffer_handler",
  "create_async_handler",
  "create_conditional_handler",
  "create_sampling_handler",
  # Types
  "EventDict",
  "EventHandler",
  # Domain namespaces
  "logging",
  "tracing",
  "metrics",
]
