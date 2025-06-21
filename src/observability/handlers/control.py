"""
Control handlers for event flow modification.

Handlers that modify event processing flow without consuming events directly.
These implement policies like filtering, sampling, and asynchronous execution
while preserving the handler interface for composition.
"""

import atexit
import queue
import random
import threading
import time
from typing import Callable, List, Optional

from ..types import EventDict, EventHandler
from .base import get_handler_name, safe_handler_call


def filtered(predicate: Callable[[EventDict], bool], handler: EventHandler) -> EventHandler:
  """
  Process events only when predicate returns True.

  Creates a conditional handler that evaluates each event against a predicate
  function. Events passing the predicate are forwarded to the wrapped handler;
  others are silently discarded.

  Args:
      predicate: Function returning True for events to process
      handler: Handler to receive matching events

  Returns:
      Filtered handler

  Example:
      error_handler = filtered(
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

  filtered_handler.__name__ = f"filtered({predicate.__name__} -> {get_handler_name(handler)})"
  return filtered_handler


def sampled(rate: float, handler: EventHandler, seed: Optional[int] = None) -> EventHandler:
  """
  Process events at specified sampling rate.

  Randomly samples events based on the provided rate, forwarding only a
  statistical subset to the wrapped handler. Useful for reducing data volume
  while maintaining representative samples.

  Args:
      rate: Sampling rate (0.0 to 1.0)
      handler: Handler for sampled events
      seed: Random seed for reproducible sampling

  Returns:
      Sampling handler

  Raises:
      ValueError: If rate is not between 0.0 and 1.0

  Example:
      # Process 1% of events
      metrics = sampled(0.01, metrics_handler)
  """
  if not 0.0 <= rate <= 1.0:
    raise ValueError(f"Rate must be 0.0 to 1.0, got {rate}")

  rng = random.Random(seed)

  def sampling_handler(event: EventDict) -> None:
    if rng.random() < rate:
      handler(event)

  sampling_handler.__name__ = f"sampled({rate:.1%} -> {get_handler_name(handler)})"
  return sampling_handler


class _AsyncHandlerWorker:
  """Internal worker for async event processing."""

  __slots__ = ("handler", "queue", "shutdown_event", "thread")

  def __init__(self, handler: EventHandler, queue_size: int):
    self.handler = handler
    self.queue = queue.SimpleQueue()
    self.shutdown_event = threading.Event()
    self.thread = threading.Thread(target=self._process_events, daemon=True)
    self.thread.start()

  def _process_events(self) -> None:
    """Process events until shutdown."""
    while not self.shutdown_event.is_set() or not self.queue.empty():
      try:
        # Timeout allows checking shutdown
        event = self.queue.get(timeout=0.1)
        self.handler(event)
      except queue.Empty:
        continue
      except Exception as e:
        safe_handler_call(get_handler_name(self.handler), "processing", e)

  def submit(self, event: EventDict, queue_size: int) -> None:
    """Submit event for async processing."""
    # Drop oldest if queue full
    while self.queue.qsize() >= queue_size:
      try:
        self.queue.get_nowait()
      except queue.Empty:
        break

    self.queue.put(event)

  def shutdown(self) -> None:
    """Gracefully stop processing."""
    self.shutdown_event.set()
    self.thread.join(timeout=5.0)


def async_handler(handler: EventHandler, queue_size: int = 10000) -> EventHandler:
  """
  Process events asynchronously in background thread.

  Decouples event emission from processing by queuing events for background
  execution. Prevents slow handlers from blocking the emission path.

  Args:
      handler: Handler to run asynchronously
      queue_size: Maximum queued events before dropping oldest

  Returns:
      Async handler with shutdown() method

  Example:
      # Non-blocking file writes
      async_file = async_handler(file_handler, queue_size=50000)
  """
  worker = _AsyncHandlerWorker(handler, queue_size)

  def async_wrapper(event: EventDict) -> None:
    worker.submit(event, queue_size)

  # Attach shutdown method
  async_wrapper.shutdown = worker.shutdown
  async_wrapper.__name__ = f"async({get_handler_name(handler)})"

  # Register cleanup
  atexit.register(worker.shutdown)

  return async_wrapper


def transformed(transform: Callable[[EventDict], EventDict], handler: EventHandler) -> EventHandler:
  """
  Transform events before processing.

  Applies a transformation function to modify events before passing them to
  the wrapped handler. Enables event enrichment, field redaction, or format
  conversion without modifying the event source.

  Args:
      transform: Function that modifies and returns event
      handler: Handler to receive transformed events

  Returns:
      Transforming handler

  Example:
      # Add request context to all events
      enriched = transformed(
          lambda e: {**e, 'service': 'api', 'version': '1.0'},
          file_handler
      )

      # Redact sensitive fields
      sanitized = transformed(
          lambda e: {k: '***' if k == 'password' else v
                     for k, v in e.items()},
          log_handler
      )
  """

  def transform_handler(event: EventDict) -> None:
    try:
      transformed_event = transform(event)
      handler(transformed_event)
    except Exception as e:
      safe_handler_call(f"transform.{get_handler_name(transform)}", "transformation", e)

  transform_handler.__name__ = f"transformed({get_handler_name(transform)} -> {get_handler_name(handler)})"
  return transform_handler


class _BatchWorker:
  """Internal worker for batch event processing."""

  __slots__ = ("handler", "batch_size", "timeout", "batch", "lock", "timer", "shutdown_event")

  def __init__(self, handler: EventHandler, batch_size: int, timeout: float):
    self.handler = handler
    self.batch_size = batch_size
    self.timeout = timeout
    self.batch: List[EventDict] = []
    self.lock = threading.Lock()
    self.timer: Optional[threading.Timer] = None
    self.shutdown_event = threading.Event()

  def add_event(self, event: EventDict) -> None:
    """Add event to batch, flushing if size reached."""
    with self.lock:
      if self.shutdown_event.is_set():
        return

      self.batch.append(event)

      # Check if batch full
      if len(self.batch) >= self.batch_size:
        self._flush_locked()
      elif len(self.batch) == 1:
        # First event in batch - start timer
        self._start_timer_locked()

  def _start_timer_locked(self) -> None:
    """Start flush timer (must hold lock)."""
    if self.timer is None and not self.shutdown_event.is_set():
      self.timer = threading.Timer(self.timeout, self._timeout_flush)
      self.timer.daemon = True
      self.timer.start()

  def _timeout_flush(self) -> None:
    """Flush batch on timeout."""
    with self.lock:
      self._flush_locked()

  def _flush_locked(self) -> None:
    """Flush current batch (must hold lock)."""
    if not self.batch:
      return

    # Cancel timer if running
    if self.timer:
      self.timer.cancel()
      self.timer = None

    # Process batch
    batch_to_process = self.batch.copy()
    self.batch.clear()

    # Release lock before processing
    self.lock.release()
    try:
      for event in batch_to_process:
        try:
          self.handler(event)
        except Exception as e:
          safe_handler_call(get_handler_name(self.handler), "batch processing", e)
    finally:
      self.lock.acquire()

  def flush(self) -> None:
    """Force flush of pending events."""
    with self.lock:
      self._flush_locked()

  def shutdown(self) -> None:
    """Shutdown worker and flush remaining events."""
    self.shutdown_event.set()

    with self.lock:
      if self.timer:
        self.timer.cancel()
        self.timer = None
      self._flush_locked()


def batched(handler: EventHandler, batch_size: int = 100, timeout: float = 1.0) -> EventHandler:
  """
  Process events in batches for efficiency.

  Accumulates events until batch_size is reached or timeout expires,
  then processes all events in the batch. Useful for operations that
  benefit from bulk processing like database inserts or API calls.

  Args:
      handler: Handler to process event batches
      batch_size: Maximum events before automatic flush
      timeout: Maximum seconds before timeout flush

  Returns:
      Batching handler with flush() and shutdown() methods

  Example:
      # Batch database writes for efficiency
      db_batch = batched(db_handler, batch_size=1000, timeout=5.0)

      # Force flush when needed
      db_batch.flush()
  """
  if batch_size <= 0:
    raise ValueError(f"batch_size must be positive, got {batch_size}")
  if timeout <= 0:
    raise ValueError(f"timeout must be positive, got {timeout}")

  worker = _BatchWorker(handler, batch_size, timeout)

  def batch_wrapper(event: EventDict) -> None:
    worker.add_event(event)

  # Attach control methods
  batch_wrapper.flush = worker.flush
  batch_wrapper.shutdown = worker.shutdown
  batch_wrapper.__name__ = f"batched({get_handler_name(handler)}, size={batch_size}, timeout={timeout}s)"

  # Register cleanup
  atexit.register(worker.shutdown)

  return batch_wrapper


def rate_limited(
  handler: EventHandler, max_per_second: float = 100.0, burst_size: Optional[int] = None
) -> EventHandler:
  """
  Limit event processing rate with token bucket algorithm.

  Implements smooth rate limiting that allows burst capacity while
  maintaining long-term rate limits. Events exceeding the rate are
  silently dropped.

  Args:
      handler: Handler to rate limit
      max_per_second: Maximum sustained event rate
      burst_size: Maximum burst capacity (default: max_per_second)

  Returns:
      Rate-limited handler

  Example:
      # Limit to 10 events/second with burst of 20
      limited = rate_limited(api_handler, max_per_second=10, burst_size=20)

      # Smooth rate without bursts
      smooth = rate_limited(handler, max_per_second=100, burst_size=1)
  """
  if max_per_second <= 0:
    raise ValueError(f"max_per_second must be positive, got {max_per_second}")

  # Default burst size equals rate (1 second of events)
  if burst_size is None:
    burst_size = int(max_per_second)
  elif burst_size <= 0:
    raise ValueError(f"burst_size must be positive, got {burst_size}")

  # Token bucket state
  tokens = float(burst_size)
  last_update = time.time()
  lock = threading.Lock()

  def rate_limited_handler(event: EventDict) -> None:
    nonlocal tokens, last_update

    with lock:
      # Replenish tokens based on time elapsed
      current_time = time.time()
      elapsed = current_time - last_update
      tokens = min(burst_size, tokens + (elapsed * max_per_second))
      last_update = current_time

      # Check if we have tokens available
      if tokens >= 1.0:
        tokens -= 1.0
        # Process event outside lock
        handler(event)
      # Else silently drop the event

  rate_limited_handler.__name__ = f"rate_limited({get_handler_name(handler)}, {max_per_second}/s)"
  return rate_limited_handler
