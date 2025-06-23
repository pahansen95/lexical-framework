"""
Resource-managed handlers for persistent connections.

Handlers that maintain long-lived resources across multiple events.
"""

import sys
import atexit
import json
import threading
import time
from typing import List, Optional, TextIO

from ..types import EventDict
from .base import safe_handler_call


class ManagedFileHandler:
  """
  File handler with lifecycle management.

  Maintains an open file handle across events for efficient writes.
  """

  def __init__(
    self,
    filepath: str,
    format: str = "json",
    mode: str = "a",
    encoding: str = "utf-8",
    flush_interval: Optional[int] = 1,
    flush_time: Optional[float] = 1.0,
  ):
    self.filepath = filepath
    self.format = format
    self.mode = mode
    self.encoding = encoding
    self.flush_interval = flush_interval
    self.flush_time = flush_time

    # Session state
    self._file: Optional[TextIO] = None
    self._lock = threading.Lock()
    self._event_count = 0
    self._last_flush = time.time()
    self._is_initialized = False

  async def initialize(self) -> None:
    """Open file for writing."""
    try:
      self._file = open(self.filepath, self.mode, encoding=self.encoding)
      self._is_initialized = True
      atexit.register(self.close)
    except IOError as e:
      safe_handler_call(f"ManagedFileHandler({self.filepath})", "opening file", e)

  async def shutdown(self) -> None:
    """Close file gracefully."""
    self.close()

  def close(self) -> None:
    """Close file and release resources."""
    with self._lock:
      if self._file:
        try:
          self._file.flush()
          self._file.close()
        except IOError:
          pass
        self._file = None
      self._is_initialized = False

  def flush(self) -> None:
    """Force flush pending writes."""
    with self._lock:
      if self._file:
        try:
          self._file.flush()
          self._last_flush = time.time()
        except IOError as e:
          safe_handler_call(f"ManagedFileHandler({self.filepath})", "flushing", e)

  def __call__(self, event: EventDict) -> None:
    """Write event to file."""
    if not self._is_initialized or not self._file:
      return

    with self._lock:
      try:
        # Format based on type
        if self.format == "json":
          json.dump(event, self._file, default=str)
          self._file.write("\n")
        else:  # text format
          timestamp_ms = event["timestamp_ns"] / 1_000_000
          self._file.write(f"{timestamp_ms:8.1f}ms {event['type']}: {event['value']}\n")

        # Update counts
        self._event_count += 1

        # Check flush conditions
        should_flush = False
        if self.flush_interval and self._event_count >= self.flush_interval:
          should_flush = True
          self._event_count = 0

        if self.flush_time and (time.time() - self._last_flush) >= self.flush_time:
          should_flush = True

        if should_flush:
          self.flush()

      except Exception as e:
        safe_handler_call(f"ManagedFileHandler({self.filepath})", "writing event", e)


class BufferHandler:
  """
  In-memory buffer handler with lifecycle support.

  Stores events in memory for testing or aggregation.
  """

  def __init__(self, max_size: int = 1000):
    self.max_size = max_size
    self.events: List[EventDict] = []
    self._lock = threading.Lock()
    self._overflow_count = 0

  async def initialize(self) -> None:
    """Initialize buffer."""
    self.clear()

  async def shutdown(self) -> None:
    """Clear buffer on shutdown."""
    self.clear()

  def clear(self) -> None:
    """Clear all stored events."""
    with self._lock:
      self.events.clear()
      self._overflow_count = 0

  def get_events(self) -> List[EventDict]:
    """Get copy of stored events."""
    with self._lock:
      return self.events.copy()

  def get_overflow_count(self) -> int:
    """Get number of events dropped due to overflow."""
    return self._overflow_count

  def __call__(self, event: EventDict) -> None:
    """Store event in buffer."""
    with self._lock:
      if len(self.events) < self.max_size:
        self.events.append(event.copy())
      else:
        self._overflow_count += 1
        if __debug__ and self._overflow_count == 1:
          print(f"BufferHandler: Max size {self.max_size} reached", file=sys.stderr)

  def flush(self) -> None:
    """No-op for buffer handler."""
    pass
