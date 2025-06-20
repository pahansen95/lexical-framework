"""
Event-based instrumentation for debugging and metrics collection.

Provides a minimal interface for emitting events that can be consumed
by attached handlers for logging, metrics aggregation, or debugging.
"""

from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager
from collections import deque
import time
import sys
import threading

# Module state with thread safety
_handlers: List[Callable[[Dict[str, Any]], None]] = []
_lock = threading.Lock()

# Category filtering state
_filter_mode: Optional[str] = None  # None | 'allow' | 'block'
_filter_categories: set = set()
_category_cache: Dict[str, str] = {}

# Timestamp configuration
_timestamp_mode: str = "relative"  # 'relative' | 'absolute' | 'both'
_start_time_ns: Optional[int] = None

# Event pooling state
_event_pool: Optional[deque] = None
_pool_size: int = 1000
_pool_enabled: bool = True
_pool_lock = threading.Lock()

# Public API


def emit(event_type: str, value: Any, **context) -> None:
  """
  Emit an event with optional context.

  Args:
    event_type: Dot-notation event identifier (e.g. 'rule.enter')
    value: Primary event value (rule name, duration, token, etc.)
    **context: Additional key-value context
  """
  # Fast path: no work if no handlers
  if not _handlers:
    return

  # Category filtering
  if _filter_mode:
    category = _get_category(event_type)
    if _filter_mode == "allow" and category not in _filter_categories:
      return
    elif _filter_mode == "block" and category in _filter_categories:
      return

  # Get event object (pooled or new)
  event = _get_event()
  pooled = event is not None

  if not pooled:
    event = {}

  # Populate event
  event["type"] = event_type
  event["value"] = value

  # Add timestamp based on mode
  if _timestamp_mode == "relative":
    event["timestamp_ms"] = _get_relative_timestamp_ms()
  elif _timestamp_mode == "absolute":
    event["timestamp"] = time.perf_counter_ns()
  else:  # both
    abs_time = time.perf_counter_ns()
    event["timestamp"] = abs_time
    event["timestamp_ms"] = _format_timestamp_ms(abs_time - (_start_time_ns or abs_time))

  # Add context
  for k, v in context.items():
    event[k] = v

  # Snapshot handlers to avoid holding lock during dispatch
  with _lock:
    handlers = _handlers.copy()

  # Dispatch to handlers - errors logged but never affect caller
  for handler in handlers:
    try:
      handler(event)
    except Exception as e:
      if __debug__:
        # In debug mode, log handler errors to stderr
        print(f"Handler error in {handler.__name__}: {e}", file=sys.stderr)
      # Continue processing other handlers

  # Return to pool if borrowed
  if pooled:
    _return_event(event)


def attach(handler: Callable[[Dict[str, Any]], None]) -> None:
  """
  Attach an event handler.

  Args:
    handler: Callable that accepts event dictionary

  Raises:
    TypeError: If handler is not callable
  """
  if not callable(handler):
    raise TypeError(f"Handler must be callable, got {type(handler).__name__}")

  with _lock:
    _handlers.append(handler)


def detach(handler: Callable[[Dict[str, Any]], None]) -> None:
  """
  Detach an event handler.

  Args:
    handler: Previously attached handler
  """
  with _lock:
    try:
      _handlers.remove(handler)
    except ValueError:
      pass  # Handler not attached, ignore


def clear() -> None:
  """Remove all handlers."""
  with _lock:
    _handlers.clear()


def get_handler_count() -> int:
  """Return number of attached handlers for debugging."""
  with _lock:
    return len(_handlers)


# Category filtering API


def enable_categories(*categories: str) -> None:
  """Enable only specified event categories."""
  global _filter_mode
  _filter_mode = "allow"
  _filter_categories.update(categories)


def disable_categories(*categories: str) -> None:
  """Disable specified event categories."""
  global _filter_mode
  _filter_mode = "block"
  _filter_categories.update(categories)


def reset_filters() -> None:
  """Clear all category filters."""
  global _filter_mode
  _filter_mode = None
  _filter_categories.clear()


# Timestamp configuration API


def set_timestamp_mode(mode: str) -> None:
  """
  Set timestamp mode.

  Args:
    mode: 'relative' (ms since start), 'absolute' (ns), or 'both'
  """
  global _timestamp_mode
  if mode not in ("relative", "absolute", "both"):
    raise ValueError(f"Invalid timestamp mode: {mode}")
  _timestamp_mode = mode


# Event pooling configuration


def configure_pool(size: int = 1000, enabled: bool = True) -> None:
  """
  Configure event pooling behavior.

  Args:
    size: Maximum pool size
    enabled: Whether pooling is enabled
  """
  global _pool_size, _pool_enabled, _event_pool

  _pool_size = size
  _pool_enabled = enabled

  if not enabled and _event_pool is not None:
    # Disable pooling
    with _pool_lock:
      _event_pool = None


# Context managers


@contextmanager
def timed(event_type: str, **context):
  """
  Context manager to time a block of code.

  Example:
    with timed('parse.duration', rule='expression'):
      result = parse_expression()
  """
  start = time.perf_counter_ns()
  try:
    yield
  finally:
    duration_ns = time.perf_counter_ns() - start
    duration_ms = duration_ns / 1_000_000
    emit(event_type, duration_ms, **context)


@contextmanager
def traced(enter_type: str, exit_type: str, name: str, **context):
  """
  Context manager to trace entry/exit of a block.

  Example:
    with traced('rule.enter', 'rule.exit', 'expression'):
      parse_expression()
  """
  emit(enter_type, name, **context)
  try:
    yield
    emit(exit_type, name, success=True, **context)
  except Exception as e:
    emit(exit_type, name, success=False, error=str(e), **context)
    raise


# Internal helpers


def _get_category(event_type: str) -> str:
  """Extract category from event type with caching."""
  if event_type not in _category_cache:
    _category_cache[event_type] = event_type.split(".")[0]
  return _category_cache[event_type]


def _get_relative_timestamp_ms() -> float:
  """Get milliseconds since first event."""
  global _start_time_ns

  now = time.perf_counter_ns()

  if _start_time_ns is None:
    _start_time_ns = now
    return 0.0

  return (now - _start_time_ns) / 1_000_000


def _format_timestamp_ms(ns: int) -> float:
  """Convert nanoseconds to milliseconds with 3 decimal precision."""
  return round(ns / 1_000_000, 3)


def _get_event() -> Optional[dict]:
  """Get event from pool or return None."""
  global _event_pool

  if not _pool_enabled:
    return None

  # Lazy initialization
  if _event_pool is None:
    with _pool_lock:
      if _event_pool is None:  # Double-check pattern
        _event_pool = deque(maxlen=_pool_size)
        # Pre-populate pool
        for _ in range(_pool_size):
          _event_pool.append({})

  # Try to get event without blocking
  try:
    return _event_pool.popleft()
  except IndexError:
    return None  # Pool exhausted


def _return_event(event: dict) -> None:
  """Return event to pool after use."""
  if _event_pool is not None:
    # Clear event for reuse
    event.clear()

    try:
      _event_pool.append(event)
    except Exception:
      pass  # Pool full, let GC handle it
