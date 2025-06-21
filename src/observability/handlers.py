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

import atexit
import queue
import sys
import threading
import time
import json
import random
from typing import Callable, List, Optional, TextIO

from .types import EventDict, EventHandler


# Resource Management for I/O
class ManagedFileHandler:
  """
  File handler with session-based resource management.

  Keeps file open during handler lifetime for efficient writes,
  with configurable flushing behavior.
  """

  def __init__(
    self,
    filepath: str,
    format: str = "json",
    mode: str = "a",
    encoding: str = "utf-8",
    flush_interval: Optional[int] = 1,  # Flush every N events
    flush_time: Optional[float] = 1.0,  # Or every N seconds
  ):
    self.filepath = filepath
    self.format = format
    self.mode = mode
    self.encoding = encoding
    self.flush_interval = flush_interval
    self.flush_time = flush_time

    # Session state
    self._file = None
    self._lock = threading.Lock()
    self._event_count = 0
    self._last_flush = time.time()

    # Open file and register cleanup
    self._open()
    atexit.register(self._close)

  def _open(self):
    """Open file for writing."""
    try:
      self._file = open(self.filepath, self.mode, encoding=self.encoding)
    except IOError as e:
      if __debug__:
        print(f"Failed to open {self.filepath}: {e}", file=sys.stderr)
      self._file = None

  def _close(self):
    """Close file gracefully."""
    with self._lock:
      if self._file:
        try:
          self._file.flush()
          self._file.close()
        except IOError:
          pass  # Best effort
        self._file = None

  def __call__(self, event: EventDict) -> None:
    """Process event with session-based file writing."""
    if not self._file:
      return  # Failed to open, fail silently

    with self._lock:
      try:
        # Write event
        if self.format == "json":
          json.dump(event, self._file, default=str)
          self._file.write("\n")
        else:
          # Human-readable format
          timestamp_ms = event["timestamp_ns"] / 1_000_000
          self._file.write(f"[{timestamp_ms:8.1f}ms] {event['type']}: {event['value']}")

          # Add context
          context_items = []
          for key, value in event.items():
            if key not in {"type", "value", "timestamp_ns"}:
              context_items.append(f"{key}={value}")

          if context_items:
            self._file.write(f" ({', '.join(context_items)})")

          self._file.write("\n")

        # Flush logic
        self._event_count += 1
        current_time = time.time()

        should_flush = False
        if self.flush_interval and self._event_count >= self.flush_interval:
          should_flush = True
          self._event_count = 0

        if self.flush_time and (current_time - self._last_flush) >= self.flush_time:
          should_flush = True

        if should_flush:
          self._file.flush()
          self._last_flush = current_time

      except IOError as e:
        if __debug__:
          print(f"Failed to write to {self.filepath}: {e}", file=sys.stderr)
        # Consider closing the file on write errors
        self._close()


class BufferHandler:
  """
  Memory buffer handler with consistent interface.

  Provides both handler interface and buffer access methods.
  """

  def __init__(self, max_size: int = 1000, overflow_policy: str = "ring"):
    """
    Initialize buffer handler.

    Args:
        max_size: Maximum events to buffer
        overflow_policy: 'ring' (overwrite oldest) or 'drop' (ignore new)
    """
    if overflow_policy not in ("ring", "drop"):
      raise ValueError(f"Invalid overflow_policy: {overflow_policy}")

    self.max_size = max_size
    self.overflow_policy = overflow_policy
    self._events = []
    self._lock = threading.Lock()
    self._start_index = 0  # For ring buffer behavior

  def __call__(self, event: EventDict) -> None:
    """Add event to buffer."""
    with self._lock:
      if self.overflow_policy == "ring":
        if len(self._events) < self.max_size:
          self._events.append(event.copy())
        else:
          # Overwrite oldest
          self._events[self._start_index] = event.copy()
          self._start_index = (self._start_index + 1) % self.max_size
      else:  # drop
        if len(self._events) < self.max_size:
          self._events.append(event.copy())
        # Else silently drop

  def get_events(self) -> List[EventDict]:
    """Retrieve buffered events in order."""
    with self._lock:
      if self.overflow_policy == "ring" and len(self._events) == self.max_size:
        # Return in correct order for ring buffer
        return self._events[self._start_index :] + self._events[: self._start_index]
      else:
        return self._events.copy()

  def clear(self) -> None:
    """Clear all buffered events."""
    with self._lock:
      self._events.clear()
      self._start_index = 0


# Sink Handlers
def print_handler(
  stream: TextIO = sys.stdout, format: str = "{timestamp_ms:8.1f}ms {type}: {value}", include_context: bool = True
) -> EventHandler:
  """
  Create console output handler.

  Args:
      stream: Output stream
      format: Format string with event fields
      include_context: Append additional fields

  Returns:
      Handler that prints to stream
  """

  def handler(event: EventDict) -> None:
    try:
      # Prepare format dict
      fmt_dict = event.copy()
      fmt_dict["timestamp_ms"] = event["timestamp_ns"] / 1_000_000

      # Format message
      message = format.format(**fmt_dict)

      # Add context if requested
      if include_context:
        context_items = []
        exclude = {"type", "value", "timestamp_ns"}
        for key, value in event.items():
          if key not in exclude and key not in format:
            context_items.append(f"{key}={value}")

        if context_items:
          message += f" ({', '.join(context_items)})"

      print(message, file=stream)

    except Exception as e:
      if __debug__:
        print(f"Print handler error: {e}", file=sys.stderr)

  handler.__name__ = f"print_handler(stream={stream.name})"
  return handler


def json_handler(stream: TextIO = sys.stdout, pretty: bool = False) -> EventHandler:
  """
  Create JSON output handler.

  Args:
      stream: Output stream
      pretty: Pretty-print JSON

  Returns:
      Handler that outputs JSON
  """

  def handler(event: EventDict) -> None:
    try:
      if pretty:
        json.dump(event, stream, default=str, indent=2)
      else:
        json.dump(event, stream, default=str)
      stream.write("\n")
      stream.flush()

    except Exception as e:
      if __debug__:
        print(f"JSON handler error: {e}", file=sys.stderr)

  handler.__name__ = f"json_handler(stream={stream.name})"
  return handler


# Control Handlers
def filtered(predicate: Callable[[EventDict], bool], handler: EventHandler) -> EventHandler:
  """
  Process events only when predicate returns True.

  Args:
      predicate: Filter function
      handler: Handler for matching events

  Returns:
      Filtered handler
  """

  def filtered_handler(event: EventDict) -> None:
    try:
      if predicate(event):
        handler(event)
    except Exception as e:
      if __debug__:
        print(f"Filter error: {e}", file=sys.stderr)

  filtered_handler.__name__ = f"filtered({predicate.__name__} -> {handler.__name__})"
  return filtered_handler


def sampled(rate: float, handler: EventHandler, seed: Optional[int] = None) -> EventHandler:
  """
  Process events at specified sampling rate.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler for sampled events
      seed: Random seed for reproducibility

  Returns:
      Sampling handler
  """
  if not 0.0 <= rate <= 1.0:
    raise ValueError(f"Rate must be 0.0 to 1.0, got {rate}")

  rng = random.Random(seed)

  def sampling_handler(event: EventDict) -> None:
    if rng.random() < rate:
      handler(event)

  sampling_handler.__name__ = f"sampled({rate:.1%} -> {handler.__name__})"
  return sampling_handler


def async_handler(handler: EventHandler, queue_size: int = 10000) -> EventHandler:
  """
  Process events asynchronously in background thread.

  Args:
      handler: Handler to run asynchronously
      queue_size: Maximum queued events

  Returns:
      Async handler with shutdown() method
  """
  q = queue.SimpleQueue()
  shutdown_event = threading.Event()

  def worker():
    """Process events until shutdown."""
    while not shutdown_event.is_set() or not q.empty():
      try:
        # Timeout allows checking shutdown
        event = q.get(timeout=0.1)
        handler(event)
      except queue.Empty:
        continue
      except Exception as e:
        if __debug__:
          print(f"Async worker error: {e}", file=sys.stderr)

  # Start worker thread
  thread = threading.Thread(target=worker, daemon=True)
  thread.start()

  def async_wrapper(event: EventDict) -> None:
    # Drop oldest if queue full
    while q.qsize() >= queue_size:
      try:
        q.get_nowait()
      except queue.Empty:
        break

    q.put(event)

  def shutdown():
    """Gracefully stop processing."""
    shutdown_event.set()
    thread.join(timeout=5.0)

  # Attach methods
  async_wrapper.shutdown = shutdown
  async_wrapper.__name__ = f"async({handler.__name__})"

  # Register cleanup
  atexit.register(shutdown)

  return async_wrapper


# Composite Handlers
def fanout(*handlers: EventHandler) -> EventHandler:
  """
  Broadcast events to multiple handlers.

  Each handler processes events independently.
  Errors in one handler don't affect others.

  Args:
      *handlers: Handlers to receive events

  Returns:
      Composite handler
  """

  def fanout_handler(event: EventDict) -> None:
    for handler in handlers:
      try:
        handler(event)
      except Exception as e:
        if __debug__:
          print(f"Fanout error in {handler.__name__}: {e}", file=sys.stderr)

  names = [h.__name__ for h in handlers]
  fanout_handler.__name__ = f"fanout({', '.join(names)})"
  return fanout_handler


# Convenience factories
def create_file_handler(filepath: str, **kwargs) -> ManagedFileHandler:
  """Create a managed file handler."""
  return ManagedFileHandler(filepath, **kwargs)


def create_buffer_handler(max_size: int = 1000, **kwargs) -> BufferHandler:
  """Create a buffer handler."""
  return BufferHandler(max_size, **kwargs)


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
]
