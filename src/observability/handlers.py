"""
Handler implementations and composition utilities.

This module provides the building blocks for processing events emitted by the
observability system. Handlers transform the raw event stream into useful outputs
through formatting, aggregation, filtering, and export.

Mental Model:
Handlers are event processors that form a pipeline. Like Unix pipes, simple
handlers combine to create sophisticated processing chains. Each handler does
one thing well - format text, write files, aggregate statistics, or filter noise.

Key Concepts:
- Handler: Function that processes EventDict instances
- Composition: Handlers wrap or chain to build complex behavior
- Filtering: Conditional handlers process selective events
- Buffering: Async handlers decouple emission from processing

Design Principles:
- Single responsibility per handler
- Composable through standard patterns
- Non-blocking event processing
- Graceful error handling

Performance Characteristics:
- Synchronous handlers block emission (use for critical paths)
- Async handlers add ~100ns queue overhead
- Sampling reduces data volume linearly
- Buffer handlers trade memory for latency
"""

import atexit
import queue
import sys
import threading
import time
import json
import random
from collections import deque
from typing import Callable, Deque, List, Optional, TextIO, TypedDict
from typing_extensions import NotRequired

from .types import EventDict, EventHandler, HandlerFilter


# Configuration types for handlers
class PrintHandlerConfig(TypedDict):
  """Configuration for print handlers."""

  prefix: NotRequired[str]
  stream: NotRequired[TextIO]
  include_timestamp: NotRequired[bool]


class FileHandlerConfig(TypedDict):
  """Configuration for file handlers."""

  mode: NotRequired[str]
  encoding: NotRequired[str]
  buffering: NotRequired[int]


class BufferHandlerConfig(TypedDict):
  """Configuration for buffer handlers."""

  max_size: NotRequired[int]
  overflow_policy: NotRequired[str]  # 'drop_oldest' | 'drop_newest' | 'block'


# Basic handlers
def create_textio_handler(
  stream: TextIO, format_fn: Optional[Callable[[EventDict], str]] = None, prefix: str = "", flush: bool = True
) -> EventHandler:
  """
  Create a handler that writes formatted events to any TextIO stream.

  Provides flexible text output to files, stdout/stderr, StringIO, or any
  TextIO-compatible object. Supports custom formatting and automatic flushing.

  Args:
      stream: TextIO stream to write to
      format_fn: Optional formatter function (defaults to JSON lines)
      prefix: Only process events with types starting with this prefix
      flush: Automatically flush after each write

  Returns:
      Handler that writes to the provided stream

  Example:
      # Write JSON to file
      with open('events.jsonl', 'w') as f:
          handler = create_textio_handler(f)
          attach(handler)

      # Custom formatting to stderr
      def format_error(event):
          return f"ERROR: {event['value']}\\n"
      handler = create_textio_handler(sys.stderr, format_error, prefix='log.40')
  """

  # Default formatter: JSON lines
  if format_fn is None:

    def format_fn(event: EventDict) -> str:
      return json.dumps(event, default=str) + "\n"

  def textio_handler(event: EventDict) -> None:
    # Filter by prefix if specified
    if prefix and not event["type"].startswith(prefix):
      return

    try:
      # Format and write
      output = format_fn(event)
      stream.write(output)

      if flush and hasattr(stream, "flush"):
        stream.flush()

    except Exception as e:
      if __debug__:
        # Attempt to log error without recursion
        try:
          sys.stderr.write(f"TextIO handler error: {e}\\n")
        except Exception:
          pass  # Give up silently

  textio_handler.__name__ = f"textio_handler(stream={getattr(stream, 'name', repr(stream))})"
  return textio_handler


def create_print_handler(
  prefix: str = "", stream: Optional[TextIO] = None, include_timestamp: bool = True
) -> EventHandler:
  """
  Create a handler that prints human-readable events to a stream.

  Args:
      prefix: Only process events with types starting with this prefix
      stream: Output stream (defaults to stdout)
      include_timestamp: Include relative timestamp in output

  Returns:
      Handler that prints formatted events
  """
  output_stream = stream or sys.stdout

  def print_handler(event: EventDict) -> None:
    # Filter by prefix if specified
    if prefix and not event["type"].startswith(prefix):
      return

    # Format timestamp
    timestamp_str = ""
    if include_timestamp:
      timestamp_ms = event["timestamp_ns"] / 1_000_000
      timestamp_str = f"[{timestamp_ms:8.1f}ms] "

    # Build output
    output = f"{timestamp_str}{event['type']}: {event['value']}"

    # Add context fields
    context_items = []
    exclude_keys = {"type", "value", "timestamp_ns"}
    for key, value in event.items():
      if key not in exclude_keys:
        context_items.append(f"{key}={value}")

    if context_items:
      output += f" ({', '.join(context_items)})"

    print(output, file=output_stream)

  print_handler.__name__ = f"print_handler(prefix='{prefix}')"
  return print_handler


def create_file_handler(filepath: str, mode: str = "a", encoding: str = "utf-8", format: str = "json") -> EventHandler:
  """
  Create a handler that writes events to a file.

  Args:
      filepath: Path to output file
      mode: File open mode ('a' for append, 'w' for overwrite)
      encoding: Text encoding
      format: Output format ('json' or 'text')

  Returns:
      Handler that writes events to file
  """

  def file_handler(event: EventDict) -> None:
    try:
      with open(filepath, mode, encoding=encoding) as f:
        if format == "json":
          # Machine-readable JSON format
          json.dump(event, f, default=str)
          f.write("\n")
        else:
          # Human-readable text format
          timestamp_ms = event["timestamp_ns"] / 1_000_000
          f.write(f"[{timestamp_ms:8.1f}ms] {event['type']}: {event['value']}")

          # Add context
          context_items = []
          exclude_keys = {"type", "value", "timestamp_ns"}
          for key, value in event.items():
            if key not in exclude_keys:
              context_items.append(f"{key}={value}")

          if context_items:
            f.write(f" ({', '.join(context_items)})")

          f.write("\n")

    except IOError as e:
      if __debug__:
        print(f"Failed to write to {filepath}: {e}", file=sys.stderr)

  file_handler.__name__ = f"file_handler('{filepath}')"
  return file_handler


def create_buffer_handler(
  max_size: int = 1000, overflow_policy: str = "drop_oldest"
) -> tuple[EventHandler, Callable[[], List[EventDict]]]:
  """
  Create a handler that buffers events in memory.

  Args:
      max_size: Maximum number of events to buffer
      overflow_policy: What to do when buffer is full
          - 'drop_oldest': Remove oldest events (ring buffer)
          - 'drop_newest': Ignore new events when full

  Returns:
      (handler, get_events) tuple where get_events retrieves buffered events
  """
  if overflow_policy not in ("drop_oldest", "drop_newest"):
    raise ValueError(f"Invalid overflow_policy: {overflow_policy}")

  if overflow_policy == "drop_oldest":
    buffer: Deque[EventDict] = deque(maxlen=max_size)
  else:
    buffer = deque()

  lock = threading.Lock()

  def buffer_handler(event: EventDict) -> None:
    with lock:
      if overflow_policy == "drop_newest" and len(buffer) >= max_size:
        return  # Drop this event

      # Store copy to prevent external mutations
      buffer.append(event.copy())

  def get_events() -> List[EventDict]:
    """Retrieve all buffered events."""
    with lock:
      return list(buffer)

  buffer_handler.__name__ = f"buffer_handler(size={max_size})"
  return buffer_handler, get_events


# Composition handlers
def create_async_handler(handler: EventHandler, queue_size: int = 10000, timeout: float = 0.1) -> EventHandler:
  """
  Create an async handler that processes events in a background thread.

  Provides non-blocking event handling with automatic cleanup on exit.
  When the queue is full, oldest events are dropped.

  Args:
      handler: Synchronous handler to wrap
      queue_size: Maximum queue size
      timeout: Queue get timeout in seconds

  Returns:
      Async handler with shutdown() method
  """
  event_queue: queue.SimpleQueue[Optional[EventDict]] = queue.SimpleQueue()
  running = threading.Event()
  running.set()

  def process_events() -> None:
    """Background thread processing events."""
    while running.is_set() or not event_queue.empty():
      try:
        event = event_queue.get(timeout=timeout)
        if event is not None:
          handler(event)
      except queue.Empty:
        continue
      except Exception as e:
        if __debug__:
          print(f"Async handler error: {e}", file=sys.stderr)

  # Start background thread
  worker = threading.Thread(target=process_events, daemon=True)
  worker.start()

  def async_handler(event: EventDict) -> None:
    """Fast enqueue with drop-on-full behavior."""
    # Drop oldest if approaching limit
    while event_queue.qsize() >= queue_size:
      try:
        event_queue.get_nowait()
      except queue.Empty:
        break

    event_queue.put_nowait(event)

  def shutdown() -> None:
    """Graceful shutdown processing remaining events."""
    running.clear()
    event_queue.put(None)  # Sentinel
    worker.join(timeout=5.0)

  # Register cleanup
  atexit.register(shutdown)

  # Attach shutdown method
  async_handler.shutdown = shutdown  # type: ignore
  handler_name = getattr(handler, "__name__", "unknown")
  async_handler.__name__ = f"async({handler_name})"

  return async_handler


def create_conditional_handler(condition: HandlerFilter, handler: EventHandler) -> EventHandler:
  """
  Create a handler that only processes events matching a condition.

  Args:
      condition: Function returning True for events to process
      handler: Handler to call for matching events

  Returns:
      Conditional handler
  """

  def conditional_handler(event: EventDict) -> None:
    if condition(event):
      handler(event)

  handler_name = getattr(handler, "__name__", "unknown")
  condition_name = getattr(condition, "__name__", "lambda")
  conditional_handler.__name__ = f"conditional({condition_name} -> {handler_name})"

  return conditional_handler


def create_sampling_handler(rate: float, handler: EventHandler, seed: Optional[int] = None) -> EventHandler:
  """
  Create a handler that samples events at a given rate.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler for sampled events
      seed: Random seed for reproducible sampling

  Returns:
      Sampling handler
  """

  if not 0.0 <= rate <= 1.0:
    raise ValueError(f"Sampling rate must be between 0.0 and 1.0, got {rate}")

  rng = random.Random(seed)

  def sampling_handler(event: EventDict) -> None:
    if rng.random() < rate:
      handler(event)

  handler_name = getattr(handler, "__name__", "unknown")
  sampling_handler.__name__ = f"sampling({rate:.1%} -> {handler_name})"

  return sampling_handler


# Utility functions
def chain_handlers(*handlers: EventHandler) -> EventHandler:
  """
  Create a handler that passes events to multiple handlers.

  Args:
      *handlers: Handlers to chain

  Returns:
      Combined handler
  """

  def chained_handler(event: EventDict) -> None:
    for handler in handlers:
      try:
        handler(event)
      except Exception as e:
        if __debug__:
          handler_name = getattr(handler, "__name__", repr(handler))
          print(f"Chain handler error in {handler_name}: {e}", file=sys.stderr)

  names = [getattr(h, "__name__", "handler") for h in handlers]
  chained_handler.__name__ = f"chain({' -> '.join(names)})"

  return chained_handler


def create_rate_limited_handler(handler: EventHandler, max_per_second: float) -> EventHandler:
  """
  Create a handler that limits event processing rate.

  Args:
      handler: Handler to rate limit
      max_per_second: Maximum events per second

  Returns:
      Rate-limited handler
  """
  if max_per_second <= 0:
    raise ValueError("max_per_second must be positive")

  min_interval = 1.0 / max_per_second
  last_time = 0.0
  lock = threading.Lock()

  def rate_limited_handler(event: EventDict) -> None:
    nonlocal last_time

    with lock:
      current_time = time.time()
      elapsed = current_time - last_time

      if elapsed < min_interval:
        return  # Drop event

      last_time = current_time

    handler(event)

  handler_name = getattr(handler, "__name__", "unknown")
  rate_limited_handler.__name__ = f"rate_limited({max_per_second}/s -> {handler_name})"

  return rate_limited_handler


# Export public API
__all__ = [
  # Basic handlers
  "create_print_handler",
  "create_file_handler",
  "create_buffer_handler",
  # Composition handlers
  "create_async_handler",
  "create_conditional_handler",
  "create_sampling_handler",
  # Utilities
  "chain_handlers",
  "create_rate_limited_handler",
  # Configuration types
  "PrintHandlerConfig",
  "FileHandlerConfig",
  "BufferHandlerConfig",
]
