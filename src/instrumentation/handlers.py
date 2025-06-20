"""
Pre-built handlers for the instrumentation module.

Provides common event handlers for logging, metrics collection, and debugging.
These are optional utilities - the core instrumentation module works without them.
"""

# Standard library
import atexit
import queue
import sys
import threading
from collections import defaultdict, deque
from typing import Any, Callable, List, Optional, TextIO, Tuple

# Local imports
from .types import EventDict, EventHandler, MetricsDict

# Type aliases for clarity
MetricsHandler = Tuple[EventHandler, Callable[[], MetricsDict]]
RingBufferHandler = Tuple[EventHandler, Callable[[], List[EventDict]]]


def create_print_handler(prefix: str = "", level: Optional[str] = None) -> EventHandler:
  """
  Create a handler that prints events to stdout.

  Args:
      prefix: Only print events with types starting with this prefix
      level: Optional prefix to prepend to output (e.g. 'DEBUG')

  Returns:
      Handler function
  """

  def print_handler(event: EventDict) -> None:
    if prefix and not event["type"].startswith(prefix):
      return

    # Format timestamp if present (using % formatting for performance)
    timestamp_str: str = ""
    if "timestamp_ms" in event:
      # Relative timestamp in milliseconds
      timestamp_str = "[%8.1fms] " % event["timestamp_ms"]

    # Format output
    output: str = "%s%s: %s" % (timestamp_str, event["type"], event["value"])
    if level:
      output = "[%s] %s" % (level, output)

    # Add relevant context (exclude standard fields)
    context_items: List[str] = []
    exclude_keys: set[str] = {"type", "value", "timestamp", "timestamp_ms"}
    k: str
    v: Any
    for k, v in event.items():
      if k not in exclude_keys:
        context_items.append("%s=%s" % (k, v))

    if context_items:
      output += " (%s)" % ", ".join(context_items)

    print(output)

  # Set function name for debugging
  print_handler.__name__ = "print_handler(prefix='%s')" % prefix
  return print_handler


def create_metrics_handler() -> MetricsHandler:
  """
  Create a handler that aggregates metrics and a function to retrieve them.

  Returns:
      (handler, get_metrics) tuple
  """
  metrics: MetricsDict = {"counters": defaultdict(int), "durations": defaultdict(list), "values": defaultdict(list)}

  def metrics_handler(event: EventDict) -> None:
    event_type: str = event["type"]
    value: Any = event["value"]

    # Count all events
    metrics["counters"][event_type] += 1

    # Aggregate durations
    if event_type.endswith(".duration"):
      metrics["durations"][event_type].append(value)

    # Collect numeric values
    elif isinstance(value, (int, float)):
      metrics["values"][event_type].append(value)

  def get_metrics() -> MetricsDict:
    """Retrieve aggregated metrics."""
    result: MetricsDict = {"counters": dict(metrics["counters"]), "durations": {}, "values": {}}

    # Calculate duration stats efficiently
    name: str
    values: List[float]
    for name, values in metrics["durations"].items():
      if values:
        total: float = sum(values)
        count: int = len(values)
        result["durations"][name] = {
          "count": count,
          "total": total,
          "avg": total / count,
          "min": min(values),
          "max": max(values),
        }

    # Calculate value stats efficiently
    for name, values in metrics["values"].items():
      if values:
        total = sum(values)
        count = len(values)
        result["values"][name] = {"count": count, "sum": total, "avg": total / count}

    return result

  metrics_handler.__name__ = "metrics_handler"
  return metrics_handler, get_metrics


def create_ring_buffer(size: int = 1000) -> RingBufferHandler:
  """
  Create a handler that stores recent events in a ring buffer.

  Args:
      size: Maximum number of events to store

  Returns:
      (handler, get_events) tuple
  """
  buffer: deque[EventDict] = deque(maxlen=size)

  def ring_buffer_handler(event: EventDict) -> None:
    # Store copy to prevent external mutations
    buffer.append(event.copy())

  def get_events() -> List[EventDict]:
    """Retrieve all buffered events in chronological order."""
    return list(buffer)

  ring_buffer_handler.__name__ = "ring_buffer_handler(size=%d)" % size
  return ring_buffer_handler, get_events


def create_file_handler(filepath: str, mode: str = "a", format: str = "json") -> EventHandler:
  """
  Create a handler that writes events to a file.

  Args:
      filepath: Path to output file
      mode: File open mode ('a' for append, 'w' for overwrite)
      format: Output format ('json' or 'text')

  Returns:
      Handler function
  """
  import json

  def file_handler(event: EventDict) -> None:
    try:
      f: TextIO
      with open(filepath, mode) as f:
        if format == "json":
          # Write as JSON for machine readability
          json.dump(event, f)
          f.write("\n")
        else:
          # Human-readable format with timestamps
          timestamp_str: str = ""
          if "timestamp_ms" in event:
            timestamp_str = "[%8.1fms] " % event["timestamp_ms"]

          line: str = "%s%s: %s" % (timestamp_str, event["type"], event["value"])

          # Add context
          context_items: List[str] = []
          exclude_keys: set[str] = {"type", "value", "timestamp", "timestamp_ms"}
          k: str
          v: Any
          for k, v in event.items():
            if k not in exclude_keys:
              context_items.append("%s=%s" % (k, v))

          if context_items:
            line += " (%s)" % ", ".join(context_items)

          f.write(line + "\n")

    except IOError as e:
      if __debug__:
        print("Failed to write to %s: %s" % (filepath, e), file=sys.stderr)

  file_handler.__name__ = "file_handler('%s')" % filepath
  return file_handler


def create_conditional_handler(condition: Callable[[EventDict], bool], handler: EventHandler) -> EventHandler:
  """
  Create a handler that only processes events matching a condition.

  Args:
      condition: Function that returns True for events to process
      handler: Handler to call for matching events

  Returns:
      Conditional handler function
  """

  def conditional_handler(event: EventDict) -> None:
    if condition(event):
      handler(event)

  handler_name: str = getattr(handler, "__name__", "unknown")
  conditional_handler.__name__ = "conditional(%s)" % handler_name
  return conditional_handler


def create_sampling_handler(rate: float, handler: EventHandler) -> EventHandler:
  """
  Create a handler that samples events at a given rate.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler to call for sampled events

  Returns:
      Sampling handler function
  """
  import random

  if not 0.0 <= rate <= 1.0:
    raise ValueError("Sampling rate must be between 0.0 and 1.0, got %s" % rate)

  def sampling_handler(event: EventDict) -> None:
    if random.random() < rate:
      handler(event)

  handler_name: str = getattr(handler, "__name__", "unknown")
  sampling_handler.__name__ = "sampling(%.1f%%, %s)" % (rate * 100, handler_name)
  return sampling_handler


def create_async_handler(handler: EventHandler, maxsize: int = 10000) -> EventHandler:
  """
  Create an async handler that processes events in a background thread.

  Provides non-blocking event handling with automatic backpressure.
  When the queue is full, oldest events are dropped.

  The handler automatically registers cleanup with atexit to ensure
  graceful shutdown. For manual cleanup, call handler.shutdown().

  Args:
      handler: Synchronous handler to wrap
      maxsize: Maximum queue size

  Returns:
      Async handler function with shutdown() method

  Example:
      >>> async_handler = create_async_handler(file_handler)
      >>> instrumentation.attach(async_handler)
      >>> # Events are processed in background
      >>> # At program exit, cleanup happens automatically
      >>> # Or manually: async_handler.shutdown()
  """
  event_queue: queue.SimpleQueue[Optional[EventDict]] = queue.SimpleQueue()
  running: threading.Event = threading.Event()
  running.set()

  def process_events() -> None:
    """Background thread processing events."""
    while running.is_set() or not event_queue.empty():
      try:
        event: Optional[EventDict] = event_queue.get(timeout=0.1)
        if event is not None:
          handler(event)
      except queue.Empty:
        continue
      except Exception as e:
        if __debug__:
          print("Async handler error: %s" % e, file=sys.stderr)

  # Start background thread
  worker: threading.Thread = threading.Thread(target=process_events, daemon=True)
  worker.start()

  def async_handler(event: EventDict) -> None:
    """Fast enqueue with drop-on-full behavior."""
    # Drop oldest if full (ring buffer behavior)
    if event_queue.qsize() >= maxsize:
      try:
        event_queue.get_nowait()  # Drop oldest
      except queue.Empty:
        pass

    event_queue.put_nowait(event)

  def shutdown() -> None:
    """Graceful shutdown processing remaining events."""
    running.clear()
    # Signal end of events
    event_queue.put(None)
    # Wait for processing to complete (with timeout)
    worker.join(timeout=5.0)

  # Register cleanup
  atexit.register(shutdown)

  handler_name: str = getattr(handler, "__name__", "unknown")
  async_handler.__name__ = "async(%s)" % handler_name
  async_handler.shutdown = shutdown  # type: ignore
  return async_handler
