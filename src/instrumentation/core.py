"""
Event-based instrumentation for debugging and metrics collection.

Provides a minimal interface for emitting events that can be consumed
by attached handlers for logging, metrics aggregation, or debugging.
"""

from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager
import time
import sys
import threading
import contextvars

# Capture module import time for relative timestamps
_START_TIME_NS = time.perf_counter_ns()

# Context variables for automatic propagation
trace_id = contextvars.ContextVar("trace_id", default=None)
parse_depth = contextvars.ContextVar("parse_depth", default=0)
current_rule = contextvars.ContextVar("current_rule", default=None)
current_file = contextvars.ContextVar("current_file", default=None)


class InstrumentationState:
  """Encapsulates all mutable instrumentation state."""

  def __init__(self):
    # Handler management
    self.handlers: List[Callable[[Dict[str, Any]], None]] = []
    self.handlers_lock = threading.Lock()

    # Category filtering
    self.filter_mode: Optional[str] = None  # None | 'allow' | 'block'
    self.filter_categories: set = set()
    self.category_cache: Dict[str, str] = {}

  def reset(self):
    """Reset to initial state for testing."""
    with self.handlers_lock:
      self.handlers.clear()
    self.filter_mode = None
    self.filter_categories.clear()
    self.category_cache.clear()


# Module-level singleton
_state = InstrumentationState()


# Context management helpers
@contextmanager
def set_context(**kwargs):
  """
  Temporarily set context variables.

  Example:
    with set_context(trace_id='abc123', current_file='test.py'):
      emit('parse.start', 'beginning parse')
  """
  tokens = []
  old_values = {}

  # Set new values and save old
  for name, value in kwargs.items():
    if name in globals():
      var = globals()[name]
      if isinstance(var, contextvars.ContextVar):
        old_values[name] = var.get()
        tokens.append(var.set(value))

  try:
    yield
  finally:
    # Restore old values
    for token in tokens:
      token.var.reset(token)


@contextmanager
def increment_depth():
  """
  Context manager to track parse depth.

  Example:
    with increment_depth():
      parse_expression()  # depth automatically incremented
  """
  current = parse_depth.get()
  token = parse_depth.set(current + 1)
  try:
    yield current + 1
  finally:
    parse_depth.reset(token)


@contextmanager
def parsing_rule(rule_name: str):
  """
  Context manager to track current parsing rule.

  Example:
    with parsing_rule('expression'):
      # Events emitted here will include rule='expression'
      parse_expression_impl()
  """
  token = current_rule.set(rule_name)
  try:
    yield
  finally:
    current_rule.reset(token)


# Public API


def emit(event_type: str, value: Any, **context) -> None:
  """
  Emit an event with optional context.

  Context variables are automatically included in the event.

  Args:
    event_type: Dot-notation event identifier (e.g. 'rule.enter')
    value: Primary event value (rule name, duration, token, etc.)
    **context: Additional key-value context
  """
  # Fast path: no work if no handlers
  if not _state.handlers:
    return

  # Category filtering
  if _state.filter_mode:
    category = _get_category(event_type)
    if _state.filter_mode == "allow" and category not in _state.filter_categories:
      return
    elif _state.filter_mode == "block" and category in _state.filter_categories:
      return

  # Build event
  event = {
    "type": event_type,
    "value": value,
    "timestamp_ms": _get_timestamp_ms(),
  }

  # Add automatic context from context variables
  if tid := trace_id.get():
    event["trace_id"] = tid

  depth = parse_depth.get()
  if depth > 0:
    event["depth"] = depth

  if rule := current_rule.get():
    event["rule"] = rule

  if file := current_file.get():
    event["file"] = file

  # Add explicit context (can override automatic)
  event.update(context)

  # Snapshot handlers to avoid holding lock during dispatch
  with _state.handlers_lock:
    handlers = _state.handlers.copy()

  # Dispatch to handlers - errors logged but never affect caller
  for handler in handlers:
    try:
      handler(event)
    except Exception as e:
      if __debug__:
        # In debug mode, log handler errors to stderr
        print("Handler error in %s: %s" % (handler.__name__, e), file=sys.stderr)
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
    raise TypeError("Handler must be callable, got %s" % type(handler).__name__)

  with _state.handlers_lock:
    _state.handlers.append(handler)


def detach(handler: Callable[[Dict[str, Any]], None]) -> None:
  """
  Detach an event handler.

  Args:
    handler: Previously attached handler
  """
  with _state.handlers_lock:
    try:
      _state.handlers.remove(handler)
    except ValueError:
      pass  # Handler not attached, ignore


def clear() -> None:
  """Remove all handlers."""
  with _state.handlers_lock:
    _state.handlers.clear()


def get_handler_count() -> int:
  """Return number of attached handlers for debugging."""
  with _state.handlers_lock:
    return len(_state.handlers)


# Category filtering API


def enable_categories(*categories: str) -> None:
  """Enable only specified event categories."""
  _state.filter_mode = "allow"
  _state.filter_categories.update(categories)


def disable_categories(*categories: str) -> None:
  """Disable specified event categories."""
  _state.filter_mode = "block"
  _state.filter_categories.update(categories)


def reset_filters() -> None:
  """Clear all category filters."""
  _state.filter_mode = None
  _state.filter_categories.clear()


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
  if event_type not in _state.category_cache:
    _state.category_cache[event_type] = event_type.split(".")[0]
  return _state.category_cache[event_type]


def _get_timestamp_ms() -> float:
  """Get milliseconds since module import."""
  return (time.perf_counter_ns() - _START_TIME_NS) / 1_000_000
