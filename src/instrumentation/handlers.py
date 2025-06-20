"""
Pre-built handlers for the instrumentation module.

Provides common event handlers for logging, metrics collection, and debugging.
These are optional utilities - the core instrumentation module works without them.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import defaultdict, deque
import sys

# Type aliases for clarity
MetricsHandler = Tuple[Callable[[Dict[str, Any]], None], Callable[[], Dict[str, Any]]]
RingBufferHandler = Tuple[Callable[[Dict[str, Any]], None], Callable[[], List[Dict[str, Any]]]]


def create_print_handler(prefix: str = "", level: Optional[str] = None) -> Callable:
  """
  Create a handler that prints events to stdout.

  Args:
    prefix: Only print events with types starting with this prefix
    level: Optional prefix to prepend to output (e.g. 'DEBUG')

  Returns:
    Handler function
  """

  def print_handler(event: Dict[str, Any]) -> None:
    if prefix and not event["type"].startswith(prefix):
      return

    # Format timestamp if present (using % formatting for performance)
    timestamp_str = ""
    if "timestamp_ms" in event:
      # Relative timestamp in milliseconds
      timestamp_str = "[%8.1fms] " % event["timestamp_ms"]
    elif "timestamp" in event:
      # Absolute timestamp in nanoseconds (convert to ms for display)
      timestamp_str = "[%8.1fms] " % (event["timestamp"] / 1_000_000)

    # Format output
    output = "%s%s: %s" % (timestamp_str, event["type"], event["value"])
    if level:
      output = "[%s] %s" % (level, output)

    # Add relevant context (exclude standard fields)
    context_items = []
    exclude_keys = {"type", "value", "timestamp", "timestamp_ms"}
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
  metrics = {"counters": defaultdict(int), "durations": defaultdict(list), "values": defaultdict(list)}

  def metrics_handler(event: Dict[str, Any]) -> None:
    event_type = event["type"]
    value = event["value"]

    # Count all events
    metrics["counters"][event_type] += 1

    # Aggregate durations
    if event_type.endswith(".duration"):
      metrics["durations"][event_type].append(value)

    # Collect numeric values
    elif isinstance(value, (int, float)):
      metrics["values"][event_type].append(value)

  def get_metrics() -> Dict[str, Any]:
    """Retrieve aggregated metrics."""
    result = {"counters": dict(metrics["counters"])}

    # Calculate duration stats efficiently
    result["durations"] = {}
    for name, values in metrics["durations"].items():
      if values:
        total = sum(values)
        count = len(values)
        result["durations"][name] = {
          "count": count,
          "total": total,
          "avg": total / count,
          "min": min(values),
          "max": max(values),
        }

    # Calculate value stats efficiently
    result["values"] = {}
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
  buffer = deque(maxlen=size)

  def ring_buffer_handler(event: Dict[str, Any]) -> None:
    # Store copy to prevent external mutations
    buffer.append(event.copy())

  def get_events() -> List[Dict[str, Any]]:
    """Retrieve all buffered events in chronological order."""
    return list(buffer)

  ring_buffer_handler.__name__ = "ring_buffer_handler(size=%d)" % size
  return ring_buffer_handler, get_events


def create_file_handler(filepath: str, mode: str = "a", format: str = "json") -> Callable:
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

  def file_handler(event: Dict[str, Any]) -> None:
    try:
      with open(filepath, mode) as f:
        if format == "json":
          # Write as JSON for machine readability
          json.dump(event, f)
          f.write("\n")
        else:
          # Human-readable format with timestamps
          timestamp_str = ""
          if "timestamp_ms" in event:
            timestamp_str = "[%8.1fms] " % event["timestamp_ms"]

          line = "%s%s: %s" % (timestamp_str, event["type"], event["value"])

          # Add context
          context_items = []
          exclude_keys = {"type", "value", "timestamp", "timestamp_ms"}
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


def create_conditional_handler(condition: Callable[[Dict[str, Any]], bool], handler: Callable) -> Callable:
  """
  Create a handler that only processes events matching a condition.

  Args:
    condition: Function that returns True for events to process
    handler: Handler to call for matching events

  Returns:
    Conditional handler function
  """

  def conditional_handler(event: Dict[str, Any]) -> None:
    if condition(event):
      handler(event)

  conditional_handler.__name__ = "conditional(%s)" % handler.__name__
  return conditional_handler


def create_sampling_handler(rate: float, handler: Callable) -> Callable:
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

  def sampling_handler(event: Dict[str, Any]) -> None:
    if random.random() < rate:
      handler(event)

  sampling_handler.__name__ = "sampling(%.1f%%, %s)" % (rate * 100, handler.__name__)
  return sampling_handler
