"""
Handler implementations for event processing and output.

Handlers consume events from the observability pipeline, producing side effects
like formatted output, storage, or transmission. They form a tree-based dispatch
system where events flow from root to leaves through control nodes.

## Architecture

Events propagate through handler trees, not pipelines:

    Event → Root
             ├─→ Filter(severity >= ERROR) → FileHandler("errors.log")
             ├─→ Sample(0.01) → NetworkHandler("metrics.local")
             └─→ Async(queue=10000) → BufferHandler(size=1000)

This enables parallel paths, isolated failures, and composable behavior.

## Handler Types

**Sink Handlers**: Terminal consumers that perform I/O operations
- Manage external resources (files, sockets, memory)
- Define output formats
- Examples: print_handler, json_handler, ManagedFileHandler

**Control Handlers**: Modify execution flow without consuming events
- Implement policies (filtering, sampling, async)
- Preserve handler interface
- Examples: filtered, sampled, async_handler

**Composite Handlers**: Coordinate multiple handlers
- Enable fan-out patterns
- Isolate failure domains
- Examples: fanout

## Resource Management

**Session-Based**: Long-lived resources across events
- Amortized acquisition cost
- Configurable batching
- High-volume optimized

**Ephemeral**: Per-event resource lifecycle
- Simple implementation
- Higher overhead
- Low-volume suitable

## Error Contract

- **Isolation**: Failures never propagate
- **Degradation**: Continue after errors
- **Diagnostics**: stderr in debug mode only
- **Recovery**: Context-appropriate strategies

## Performance

| Type | Latency | Throughput |
|------|---------|------------|
| Sync I/O | 10-100μs | 10K/s |
| Async Queue | 100-500ns | 1M/s |
| Filter | 10-50ns | 10M/s |
| Sample | 50-100ns | 5M/s |
| Fanout | 10ns/target | 10M/s |

## Usage

```python
# Basic filtering
errors = filtered(lambda e: e.get('level') >= ERROR, file_handler)

# Production config
prod = fanout(
    filtered(is_critical, create_file_handler('critical.log')),
    sampled(0.01, async_handler(metrics_handler)),
    async_handler(create_file_handler('archive.log'))
)
```

## Design Principles

- Single responsibility per handler
- Composable through standard patterns
- Fail-safe operation
- Resource-efficient I/O batching
- Predictable performance characteristics
"""

# Import handlers from submodules
from .sink import print_handler, json_handler
from .control import filtered, sampled, async_handler
from .composite import fanout
from .resource import ManagedFileHandler, BufferHandler


# Convenience factories for backward compatibility
def create_file_handler(filepath: str, **kwargs) -> ManagedFileHandler:
  """Create a managed file handler."""
  return ManagedFileHandler(filepath, **kwargs)


def create_buffer_handler(max_size: int = 1000, **kwargs) -> BufferHandler:
  """Create a buffer handler."""
  return BufferHandler(max_size, **kwargs)


# Convenience factories for new handlers
def create_print_handler(**kwargs):
  """Create a print handler with custom configuration."""
  return print_handler(**kwargs)


def create_async_handler(handler, **kwargs):
  """Create an async handler wrapper."""
  return async_handler(handler, **kwargs)


def create_conditional_handler(predicate, handler):
  """Create a conditional handler (alias for filtered)."""
  return filtered(predicate, handler)


def create_sampling_handler(rate, handler, **kwargs):
  """Create a sampling handler."""
  return sampled(rate, handler, **kwargs)


# Export public API
__all__ = [
  # Classes
  "ManagedFileHandler",
  "BufferHandler",
  # Sink handlers
  "print_handler",
  "json_handler",
  # Control handlers
  "filtered",
  "sampled",
  "async_handler",
  # Composite handlers
  "fanout",
  # Factories
  "create_file_handler",
  "create_buffer_handler",
  # Additional convenience factories
  "create_print_handler",
  "create_async_handler",
  "create_conditional_handler",
  "create_sampling_handler",
]
