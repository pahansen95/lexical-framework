"""
Sink handlers for event output.

Terminal event consumers that write events to external destinations such as
console streams, files, or structured formats. These handlers perform the
final I/O operations in the event processing pipeline.
"""

import json
import sys
from typing import TextIO

from ..types import EventDict, EventHandler
from .base import format_event_simple, format_context_items, STANDARD_EXCLUSIONS


def print_handler(
  stream: TextIO = sys.stdout, format: str = "{timestamp_ms:8.1f}ms {type}: {value}", include_context: bool = True
) -> EventHandler:
  """
  Create console output handler.

  Writes formatted events to a text stream with optional context inclusion.
  Default format emphasizes readability with timestamp, type, and value.

  Args:
      stream: Output stream (default: stdout)
      format: Format string with event field placeholders
      include_context: Append additional fields as context

  Returns:
      Handler that prints formatted events

  Example:
      handler = print_handler(format="{type}: {value}")
  """

  def handler(event: EventDict) -> None:
    try:
      # Format primary message
      message = format_event_simple(event, format)

      # Add context if requested
      if include_context:
        # Extract fields not in format string
        exclude = STANDARD_EXCLUSIONS.copy()
        # Add fields already in format to exclusions
        for field in event.keys():
          if f"{{{field}}}" in format:
            exclude.add(field)

        context_items = format_context_items(event, exclude)
        if context_items:
          message += f" ({', '.join(context_items)})"

      print(message, file=stream)

    except Exception as e:
      if __debug__:
        print(f"Print handler error: {e}", file=sys.stderr)

  handler.__name__ = f"print_handler(stream={stream.name})"
  return handler


def json_handler(stream: TextIO = sys.stdout, pretty: bool = False, ensure_ascii: bool = True) -> EventHandler:
  """
  Create JSON output handler.

  Serializes events as JSON objects, one per line. Supports both
  compact and pretty-printed output formats.

  Args:
      stream: Output stream (default: stdout)
      pretty: Enable pretty-printing with indentation
      ensure_ascii: Escape non-ASCII characters

  Returns:
      Handler that outputs JSON-formatted events

  Example:
      handler = json_handler(pretty=True)
  """

  def handler(event: EventDict) -> None:
    try:
      if pretty:
        json.dump(event, stream, default=str, indent=2, ensure_ascii=ensure_ascii)
      else:
        json.dump(event, stream, default=str, ensure_ascii=ensure_ascii)

      stream.write("\n")
      stream.flush()

    except Exception as e:
      if __debug__:
        print(f"JSON handler error: {e}", file=sys.stderr)

  handler.__name__ = f"json_handler(stream={stream.name}, pretty={pretty})"
  return handler


def null_handler() -> EventHandler:
  """
  Create a no-op handler.

  Discards all events without processing. Useful for testing
  or as a placeholder in conditional configurations.

  Returns:
      Handler that discards all events
  """

  def handler(event: EventDict) -> None:
    pass

  handler.__name__ = "null_handler"
  return handler
