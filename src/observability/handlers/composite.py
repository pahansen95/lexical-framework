"""
Composite handlers for event distribution.

Handlers that coordinate multiple sub-handlers, enabling sophisticated event
routing patterns while maintaining failure isolation between components.
"""

import asyncio

from ..types import EventDict, EventHandler
from .base import get_handler_name, safe_handler_call


class FanoutHandler:
  """
  Broadcast events to multiple handlers with lifecycle support.

  Forwards each event to all provided handlers independently.
  Handler failures are isolated - an error in one handler does
  not prevent others from receiving the event.
  """

  def __init__(self, *handlers: EventHandler):
    """
    Initialize fanout handler.

    Args:
        *handlers: Variable number of handlers to receive events
    """
    self.handlers = list(handlers)

  async def initialize(self) -> None:
    """Initialize all sub-handlers that support lifecycle."""
    tasks = []
    for handler in self.handlers:
      if hasattr(handler, "initialize"):
        tasks.append(handler.initialize())

    if tasks:
      await asyncio.gather(*tasks, return_exceptions=True)

  async def shutdown(self) -> None:
    """Shutdown all sub-handlers that support lifecycle."""
    tasks = []
    for handler in self.handlers:
      if hasattr(handler, "shutdown"):
        tasks.append(handler.shutdown())

    if tasks:
      await asyncio.gather(*tasks, return_exceptions=True)

  def __call__(self, event: EventDict) -> None:
    """Forward event to all handlers."""
    for handler in self.handlers:
      try:
        handler(event)
      except Exception as e:
        safe_handler_call(f"fanout.{get_handler_name(handler)}", "processing", e)


class FallbackHandler:
  """
  Try handlers in order until one succeeds.

  Attempts to process each event with the primary handler.
  If it fails, tries each backup handler in order until one
  succeeds. Useful for ensuring event delivery with multiple
  fallback options.
  """

  def __init__(self, primary: EventHandler, *backups: EventHandler):
    """
    Initialize fallback handler.

    Args:
        primary: Primary handler to try first
        *backups: Backup handlers to try on primary failure
    """
    self.primary = primary
    self.backups = list(backups)
    self.all_handlers = [primary] + self.backups

  async def initialize(self) -> None:
    """Initialize all handlers that support lifecycle."""
    tasks = []
    for handler in self.all_handlers:
      if hasattr(handler, "initialize"):
        tasks.append(handler.initialize())

    if tasks:
      await asyncio.gather(*tasks, return_exceptions=True)

  async def shutdown(self) -> None:
    """Shutdown all handlers that support lifecycle."""
    tasks = []
    for handler in self.all_handlers:
      if hasattr(handler, "shutdown"):
        tasks.append(handler.shutdown())

    if tasks:
      await asyncio.gather(*tasks, return_exceptions=True)

  def __call__(self, event: EventDict) -> None:
    """Try handlers until one succeeds."""
    # Try primary first
    try:
      self.primary(event)
      return
    except Exception as e:
      safe_handler_call(f"fallback.primary.{get_handler_name(self.primary)}", "processing", e)

    # Try backups in order
    for i, handler in enumerate(self.backups):
      try:
        handler(event)
        return  # Success - stop trying
      except Exception as e:
        safe_handler_call(f"fallback.backup[{i}].{get_handler_name(handler)}", "processing", e)

    # All handlers failed - report in debug mode
    if __debug__:
      import sys

      print(f"All handlers failed for event type: {event.get('type', 'unknown')}", file=sys.stderr)


# Control flow functions that return simple handler functions


def filtered(predicate, handler: EventHandler) -> EventHandler:
  """
  Process events only when predicate returns True.

  Creates a conditional handler that evaluates each event against
  a predicate function. Events passing the predicate are forwarded
  to the wrapped handler; others are silently discarded.

  Args:
      predicate: Function returning True for events to process
      handler: Handler to receive matching events

  Returns:
      Filtered handler function

  Example:
      error_only = filtered(
          lambda e: e.get('level', 0) >= ERROR,
          file_handler
      )
  """

  def filtered_handler(event: EventDict) -> None:
    try:
      if predicate(event):
        handler(event)
    except Exception as e:
      safe_handler_call("Filter", "predicate evaluation", e)

  filtered_handler.__name__ = f"filtered({getattr(predicate, '__name__', 'predicate')} -> {get_handler_name(handler)})"
  return filtered_handler


def sampled(rate: float, handler: EventHandler, seed=None) -> EventHandler:
  """
  Process events at specified sampling rate.

  Randomly samples events based on the provided rate, forwarding
  only a statistical subset to the wrapped handler. Useful for
  reducing data volume while maintaining representative samples.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler for sampled events
      seed: Random seed for reproducible sampling

  Returns:
      Sampling handler function

  Raises:
      ValueError: If rate is not between 0.0 and 1.0

  Example:
      # Process 1% of events
      sampled_metrics = sampled(0.01, metrics_handler)
  """
  if not 0.0 <= rate <= 1.0:
    raise ValueError(f"Rate must be 0.0 to 1.0, got {rate}")

  import random

  rng = random.Random(seed)

  def sampling_handler(event: EventDict) -> None:
    if rng.random() < rate:
      handler(event)

  sampling_handler.__name__ = f"sampled({rate:.1%} -> {get_handler_name(handler)})"
  return sampling_handler
