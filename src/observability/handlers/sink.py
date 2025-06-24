"""
Sink handlers for event output.

Terminal event consumers that write events to external destinations.
"""

import json
import sys
from typing import TextIO

from ..types import EventDict
from .base import format_event_simple, format_context_items, STANDARD_EXCLUSIONS


class PrintHandler:
  """Console output handler with lifecycle support."""

  def __init__(
    self,
    stream: TextIO = sys.stdout,
    format: str = "{timestamp_ns:16d}ns {type}: {value}",
    include_context: bool = True,
  ):
    self.stream = stream
    self.format = format
    self.include_context = include_context
    self._is_initialized = False

  async def initialize(self) -> None:
    """Initialize handler (no-op for print handler)."""
    self._is_initialized = True

  async def shutdown(self) -> None:
    """Flush stream on shutdown."""
    if hasattr(self.stream, "flush"):
      self.stream.flush()
    self._is_initialized = False

  def __call__(self, event: EventDict) -> None:
    """Process event."""
    try:
      # Format primary message
      message = format_event_simple(event, self.format)

      # Add context if requested
      if self.include_context:
        exclude = STANDARD_EXCLUSIONS.copy()
        # Add fields already in format to exclusions
        for field in event.keys():
          if f"{{{field}}}" in self.format:
            exclude.add(field)

        context_items = format_context_items(event, exclude)
        if context_items:
          message += f" ({', '.join(context_items)})"

      print(message, file=self.stream)

    except Exception as e:
      if __debug__:
        print(f"Print handler error: {e}", file=sys.stderr)


class JsonHandler:
  """JSON output handler with lifecycle support."""

  def __init__(self, stream: TextIO = sys.stdout, pretty: bool = False, ensure_ascii: bool = True):
    self.stream = stream
    self.pretty = pretty
    self.ensure_ascii = ensure_ascii
    self._is_initialized = False

  async def initialize(self) -> None:
    """Initialize handler."""
    self._is_initialized = True

  async def shutdown(self) -> None:
    """Flush stream on shutdown."""
    if hasattr(self.stream, "flush"):
      self.stream.flush()
    self._is_initialized = False

  def __call__(self, event: EventDict) -> None:
    """Process event as JSON."""
    try:
      if self.pretty:
        json.dump(event, self.stream, default=str, indent=2, ensure_ascii=self.ensure_ascii)
      else:
        json.dump(event, self.stream, default=str, ensure_ascii=self.ensure_ascii)

      self.stream.write("\n")
      self.stream.flush()

    except Exception as e:
      if __debug__:
        print(f"JSON handler error: {e}", file=sys.stderr)


# No factory functions - use classes directly
