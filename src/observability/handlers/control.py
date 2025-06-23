"""
Control handlers for event flow modification.

Handlers that modify event processing flow without consuming events directly.
"""

import asyncio
import queue
import random
import threading
import time
import sys
from typing import Callable, Optional

from ..types import EventDict, EventHandler
from .base import get_handler_name, safe_handler_call


def filtered(predicate: Callable[[EventDict], bool], handler: EventHandler) -> EventHandler:
  """
  Process events only when predicate returns True.

  Args:
      predicate: Function returning True for events to process
      handler: Handler to receive matching events

  Returns:
      Filtered handler
  """

  def filtered_handler(event: EventDict) -> None:
    try:
      if predicate(event):
        handler(event)
    except Exception as e:
      safe_handler_call("Filter", "predicate evaluation", e)

  filtered_handler.__name__ = f"filtered({predicate.__name__} -> {get_handler_name(handler)})"

  return filtered_handler


def sampled(rate: float, handler: EventHandler, seed: Optional[int] = None) -> EventHandler:
  """
  Process events at specified sampling rate.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler for sampled events
      seed: Random seed for reproducible sampling

  Returns:
      Sampling handler
  """
  if not 0.0 <= rate <= 1.0:
    raise ValueError(f"Rate must be 0.0 to 1.0, got {rate}")

  rng = random.Random(seed)

  def sampling_handler(event: EventDict) -> None:
    if rng.random() < rate:
      handler(event)

  sampling_handler.__name__ = f"sampled({rate:.1%} -> {get_handler_name(handler)})"

  return sampling_handler


class AsyncHandlerWorker:
  """Async event processor with lifecycle management."""

  def __init__(self, handler: EventHandler, queue_size: int = 10000):
    self.handler = handler
    self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
    self.shutdown_event = threading.Event()
    self.thread: Optional[threading.Thread] = None
    self._error_count = 0
    self._max_errors = 100

  async def initialize(self) -> None:
    """Start worker thread."""
    self.thread = threading.Thread(target=self._process_events, daemon=True)
    self.thread.start()

    # Initialize wrapped handler if it supports lifecycle
    if hasattr(self.handler, "initialize"):
      await self.handler.initialize()

  async def shutdown(self) -> None:
    """Stop worker and drain queue."""
    # Signal shutdown
    self.shutdown_event.set()

    # Process remaining events with timeout
    timeout = time.time() + 5.0  # 5 second grace period
    while not self.queue.empty() and time.time() < timeout:
      await asyncio.sleep(0.1)

    # Join thread
    if self.thread:
      self.thread.join(timeout=1.0)

    # Shutdown wrapped handler
    if hasattr(self.handler, "shutdown"):
      await self.handler.shutdown()

  def _process_events(self) -> None:
    """Process events until shutdown."""
    while not self.shutdown_event.is_set():
      try:
        # Get with timeout to check shutdown periodically
        event = self.queue.get(timeout=0.1)

        try:
          self.handler(event)
        except Exception as e:
          self._error_count += 1
          safe_handler_call("AsyncHandler", "processing event", e)

          # Circuit breaker
          if self._error_count > self._max_errors:
            if __debug__:
              print(f"AsyncHandler: Too many errors ({self._error_count}), stopping", file=sys.stderr)
            break

      except queue.Empty:
        continue

  def __call__(self, event: EventDict) -> None:
    """Queue event for async processing."""
    try:
      self.queue.put_nowait(event)
    except queue.Full:
      safe_handler_call("AsyncHandler", "queue full", RuntimeError("Event queue full"))
