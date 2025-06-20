"""
Event-based instrumentation for debugging and metrics collection.

Provides a minimal interface for emitting events that can be consumed
by attached handlers for logging, metrics aggregation, or debugging.
"""

from typing import Any, Callable, Dict, List
from contextlib import contextmanager
import time
import sys
import threading

# Module state with thread safety
_handlers: List[Callable[[Dict[str, Any]], None]] = []
_lock = threading.Lock()

# Public API


def emit(event_type: str, value: Any, **context) -> None:
  """
  Emit an event with optional context.

  Args:
    event_type: Dot-notation event identifier (e.g. 'rule.enter')
    value: Primary event value (rule name, duration, token, etc.)
    **context: Additional key-value context
  """
  # Fast path: no work if no handlers (no lock needed for read)
  if not _handlers:
    return

  # Create immutable event
  event = {"type": event_type, "value": value, "timestamp": time.perf_counter_ns(), **context}

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
