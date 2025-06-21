"""
Composite handlers for event distribution.

Handlers that coordinate multiple sub-handlers, enabling sophisticated event
routing patterns while maintaining failure isolation between components.
"""

from ..types import EventDict, EventHandler
from .base import get_handler_name, safe_handler_call


def fanout(*handlers: EventHandler) -> EventHandler:
  """
  Broadcast events to multiple handlers.

  Creates a composite handler that forwards each event to all provided handlers
  independently. Handler failures are isolated - an error in one handler does
  not prevent others from receiving the event.

  Args:
      *handlers: Variable number of handlers to receive events

  Returns:
      Composite handler that broadcasts to all sub-handlers

  Example:
      production = fanout(
          file_handler,
          metrics_handler,
          alert_handler
      )
  """
  # Convert to list for consistent iteration
  handler_list = list(handlers)

  def fanout_handler(event: EventDict) -> None:
    for handler in handler_list:
      try:
        handler(event)
      except Exception as e:
        safe_handler_call(f"fanout.{get_handler_name(handler)}", "processing", e)

  # Create readable name
  names = [get_handler_name(h) for h in handler_list]
  fanout_handler.__name__ = f"fanout({', '.join(names)})"

  return fanout_handler


def fallback(primary: EventHandler, *backups: EventHandler) -> EventHandler:
  """
  Process events with fallback handlers on failure.

  Attempts to process each event with the primary handler. If it fails,
  tries each backup handler in order until one succeeds.

  Args:
      primary: Primary handler to try first
      *backups: Backup handlers to try on primary failure

  Returns:
      Handler with fallback behavior

  Example:
      reliable = fallback(
          network_handler,
          file_handler,
          print_handler  # Last resort
      )
  """
  backup_list = list(backups)

  def fallback_handler(event: EventDict) -> None:
    # Try primary first
    try:
      primary(event)
      return
    except Exception as e:
      safe_handler_call(f"fallback.primary.{get_handler_name(primary)}", "processing", e)

    # Try backups in order
    for i, handler in enumerate(backup_list):
      try:
        handler(event)
        return  # Success - stop trying
      except Exception as e:
        safe_handler_call(f"fallback.backup[{i}].{get_handler_name(handler)}", "processing", e)

    # All handlers failed - report in debug mode
    if __debug__:
      import sys

      print(f"All handlers failed for event type: {event.get('type', 'unknown')}", file=sys.stderr)

  # Create readable name
  all_names = [get_handler_name(primary)] + [get_handler_name(h) for h in backup_list]
  fallback_handler.__name__ = f"fallback({' -> '.join(all_names)})"

  return fallback_handler
