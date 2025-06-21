"""
Resource-managed handlers for persistent connections.

Handlers that maintain long-lived resources across multiple events, providing
session-based I/O operations with configurable batching and lifecycle management.
"""

import atexit
import json
import threading
import time
from typing import List, Optional

from ..types import EventDict
from .base import safe_handler_call


class ManagedFileHandler:
  """
  File handler with session-based resource management.

  Maintains an open file handle across events for efficient writes with
  configurable flush policies. Automatically handles resource cleanup
  on shutdown.
  """

  __slots__ = (
    "filepath",
    "format",
    "mode",
    "encoding",
    "flush_interval",
    "flush_time",
    "_file",
    "_lock",
    "_event_count",
    "_last_flush",
  )

  def __init__(
    self,
    filepath: str,
    format: str = "json",
    mode: str = "a",
    encoding: str = "utf-8",
    flush_interval: Optional[int] = 1,
    flush_time: Optional[float] = 1.0,
  ):
    """
    Initialize managed file handler.

    Args:
        filepath: Output file path
        format: Output format ('json' or 'text')
        mode: File open mode
        encoding: Text encoding
        flush_interval: Flush after N events (None to disable)
        flush_time: Flush after N seconds (None to disable)
    """
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

  def _open(self) -> None:
    """Open file for writing."""
    try:
      self._file = open(self.filepath, self.mode, encoding=self.encoding)
    except IOError as e:
      safe_handler_call(f"ManagedFileHandler({self.filepath})", "opening file", e)
      self._file = None

  def _close(self) -> None:
    """Close file gracefully."""
    with self._lock:
      if self._file:
        try:
          self._file.flush()
          self._file.close()
        except IOError:
          pass  # Best effort
        self._file = None

  def flush(self) -> None:
    """Force flush pending writes."""
    with self._lock:
      if self._file:
        try:
          self._file.flush()
          self._last_flush = time.time()
        except IOError as e:
          safe_handler_call(f"ManagedFileHandler({self.filepath})", "flushing", e)

  def close(self) -> None:
    """Close handler and release resources."""
    self._close()

  def __call__(self, event: EventDict) -> None:
    """Process event with session-based file writing."""
    if not self._file:
      return  # Failed to open

    with self._lock:
      try:
        # Write event based on format
        if self.format == "json":
          json.dump(event, self._file, default=str)
          self._file.write("\n")
        else:
          # Human-readable text format
          timestamp_ms = event["timestamp_ns"] / 1_000_000
          self._file.write(f"[{timestamp_ms:8.1f}ms] {event['type']}: {event['value']}")

          # Add context fields
          context_items = []
          for key, value in event.items():
            if key not in {"type", "value", "timestamp_ns"}:
              context_items.append(f"{key}={value}")

          if context_items:
            self._file.write(f" ({', '.join(context_items)})")

          self._file.write("\n")

        # Update flush tracking
        self._event_count += 1
        current_time = time.time()

        # Determine if flush needed
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
        safe_handler_call(f"ManagedFileHandler({self.filepath})", "writing", e)
        self._close()  # Close on write error


class BufferHandler:
  """
  Memory buffer handler with bounded storage.

  Provides in-memory event buffering with configurable overflow policies.
  Useful for capturing recent events for debugging or batched processing.
  """

  __slots__ = ("max_size", "overflow_policy", "_events", "_lock", "_start_index")

  def __init__(self, max_size: int = 1000, overflow_policy: str = "ring"):
    """
    Initialize buffer handler.

    Args:
        max_size: Maximum events to buffer
        overflow_policy: 'ring' (overwrite oldest) or 'drop' (ignore new)

    Raises:
        ValueError: If overflow_policy is invalid
    """
    if overflow_policy not in ("ring", "drop"):
      raise ValueError(f"Invalid overflow_policy: {overflow_policy}")

    self.max_size = max_size
    self.overflow_policy = overflow_policy
    self._events: List[EventDict] = []
    self._lock = threading.Lock()
    self._start_index = 0  # For ring buffer tracking

  def __call__(self, event: EventDict) -> None:
    """Add event to buffer."""
    with self._lock:
      if self.overflow_policy == "ring":
        if len(self._events) < self.max_size:
          # Buffer not full yet
          self._events.append(event.copy())
        else:
          # Overwrite oldest event
          self._events[self._start_index] = event.copy()
          self._start_index = (self._start_index + 1) % self.max_size
      else:  # drop policy
        if len(self._events) < self.max_size:
          self._events.append(event.copy())
        # Else silently drop new events

  def get_events(self) -> List[EventDict]:
    """
    Retrieve buffered events in chronological order.

    Returns:
        List of events from oldest to newest
    """
    with self._lock:
      if self.overflow_policy == "ring" and len(self._events) == self.max_size:
        # Return events in correct chronological order
        return self._events[self._start_index :] + self._events[: self._start_index]
      else:
        return self._events.copy()

  def clear(self) -> None:
    """Clear all buffered events."""
    with self._lock:
      self._events.clear()
      self._start_index = 0

  def __len__(self) -> int:
    """Return number of buffered events."""
    with self._lock:
      return len(self._events)
