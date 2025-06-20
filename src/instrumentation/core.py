"""
Event-based instrumentation for debugging and metrics collection.

Provides a minimal interface for emitting events that can be consumed
by attached handlers for logging, metrics aggregation, or debugging.
"""

# Standard library
import contextvars
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Final, Iterator, List, Optional

# Local imports
from .types import EventDict, EventHandler

# Capture module import time for relative timestamps
_START_TIME_NS: Final[int] = time.perf_counter_ns()

# Context variables for automatic propagation
trace_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("trace_id", default=None)
parse_depth: Final[contextvars.ContextVar[int]] = contextvars.ContextVar("parse_depth", default=0)
current_rule: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("current_rule", default=None)
current_file: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("current_file", default=None)


class InstrumentationState:
  """Encapsulates all mutable instrumentation state."""

  __slots__ = ("handlers", "handlers_lock", "filter_mode", "filter_categories", "category_cache")

  def __init__(self) -> None:
    # Handler management
    self.handlers: List[EventHandler] = []
    self.handlers_lock: threading.Lock = threading.Lock()

    # Category filtering
    self.filter_mode: Optional[str] = None  # None | 'allow' | 'block'
    self.filter_categories: set[str] = set()
    self.category_cache: Dict[str, str] = {}

  def reset(self) -> None:
    """Reset to initial state for testing."""
    with self.handlers_lock:
      self.handlers.clear()
    self.filter_mode = None
    self.filter_categories.clear()
    self.category_cache.clear()


# Module-level singleton
_state: InstrumentationState = InstrumentationState()


# Context management helpers
@contextmanager
def set_context(**kwargs: Any) -> Iterator[None]:
  """
  Temporarily set context variables.

  Example:
      with set_context(trace_id='abc123', current_file='test.py'):
          emit('parse.start', 'beginning parse')
  """
  tokens: List[contextvars.Token[Any]] = []
  old_values: Dict[str, Any] = {}

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
def increment_depth() -> Iterator[int]:
  """
  Context manager to track parse depth.

  Example:
      with increment_depth():
          parse_expression()  # depth automatically incremented
  """
  current: int = parse_depth.get()
  token: contextvars.Token[int] = parse_depth.set(current + 1)
  try:
    yield current + 1
  finally:
    parse_depth.reset(token)


@contextmanager
def parsing_rule(rule_name: str) -> Iterator[None]:
  """
  Context manager to track current parsing rule.

  Example:
      with parsing_rule('expression'):
          # Events emitted here will include rule='expression'
          parse_expression_impl()

  Args:
      rule_name: Name of the parsing rule

  Raises:
      TypeError: If rule_name is not a string
      ValueError: If rule_name is empty
  """
  # Boundary validation
  if not isinstance(rule_name, str):
    raise TypeError("rule_name must be str, got %s" % type(rule_name).__name__)
  if not rule_name:
    raise ValueError("rule_name cannot be empty")

  token: contextvars.Token[Optional[str]] = current_rule.set(rule_name)
  try:
    yield
  finally:
    current_rule.reset(token)


# Public API


def emit(event_type: str, value: Any, **context: Any) -> None:
  """
  Emit an event with optional context.

  Context variables are automatically included in the event.

  Args:
      event_type: Dot-notation event identifier (e.g. 'rule.enter')
      value: Primary event value (rule name, duration, token, etc.)
      **context: Additional key-value context

  Raises:
      TypeError: If event_type is not a string or context keys are not strings
      ValueError: If event_type is empty
  """
  # Boundary validation
  if not isinstance(event_type, str):
    raise TypeError("event_type must be str, got %s" % type(event_type).__name__)
  if not event_type:
    raise ValueError("event_type cannot be empty")

  # Validate context keys are strings
  for key in context:
    if not isinstance(key, str):
      raise TypeError("context keys must be str, got %s for key" % type(key).__name__)

  # Fast path: no work if no handlers
  if not _state.handlers:
    return

  # Category filtering
  if _state.filter_mode:
    category: str = _get_category(event_type)
    if _state.filter_mode == "allow" and category not in _state.filter_categories:
      return
    elif _state.filter_mode == "block" and category in _state.filter_categories:
      return

  # Build event as TypedDict
  event: EventDict = {
    "type": event_type,
    "value": value,
    "timestamp_ms": _get_timestamp_ms(),
  }

  # Add automatic context from context variables
  tid: Optional[str] = trace_id.get()
  if tid is not None:
    event["trace_id"] = tid

  depth: int = parse_depth.get()
  if depth > 0:
    event["depth"] = depth

  rule: Optional[str] = current_rule.get()
  if rule is not None:
    event["rule"] = rule

  file: Optional[str] = current_file.get()
  if file is not None:
    event["file"] = file

  # Add explicit context (can override automatic)
  key: str
  val: Any
  for key, val in context.items():
    event[key] = val  # type: ignore

  # Snapshot handlers to avoid holding lock during dispatch
  handlers: List[EventHandler]
  with _state.handlers_lock:
    handlers = _state.handlers.copy()

  # Dispatch to handlers - errors logged but never affect caller
  handler: EventHandler
  for handler in handlers:
    try:
      handler(event)
    except Exception as e:
      if __debug__:
        # In debug mode, log handler errors to stderr
        handler_name: str = getattr(handler, "__name__", "unknown")
        print("Handler error in %s: %s" % (handler_name, e), file=sys.stderr)
      # Continue processing other handlers


def attach(handler: EventHandler) -> None:
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


def detach(handler: EventHandler) -> None:
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
  """
  Enable only specified event categories.

  Args:
      *categories: Category names to enable

  Raises:
      TypeError: If any category is not a string
      ValueError: If any category is empty
  """
  # Boundary validation
  for cat in categories:
    if not isinstance(cat, str):
      raise TypeError("categories must be str, got %s" % type(cat).__name__)
    if not cat:
      raise ValueError("category cannot be empty")

  _state.filter_mode = "allow"
  _state.filter_categories.update(categories)


def disable_categories(*categories: str) -> None:
  """
  Disable specified event categories.

  Args:
      *categories: Category names to disable

  Raises:
      TypeError: If any category is not a string
      ValueError: If any category is empty
  """
  # Boundary validation
  for cat in categories:
    if not isinstance(cat, str):
      raise TypeError("categories must be str, got %s" % type(cat).__name__)
    if not cat:
      raise ValueError("category cannot be empty")

  _state.filter_mode = "block"
  _state.filter_categories.update(categories)


def reset_filters() -> None:
  """Clear all category filters."""
  _state.filter_mode = None
  _state.filter_categories.clear()


# Context managers


@contextmanager
def timed(event_type: str, **context: Any) -> Iterator[None]:
  """
  Context manager to time a block of code.

  Example:
      with timed('parse.duration', rule='expression'):
          result = parse_expression()

  Args:
      event_type: Event type for the duration event
      **context: Additional context for the event

  Raises:
      TypeError: If event_type is not a string
      ValueError: If event_type is empty
  """
  # Boundary validation
  if not isinstance(event_type, str):
    raise TypeError("event_type must be str, got %s" % type(event_type).__name__)
  if not event_type:
    raise ValueError("event_type cannot be empty")

  start: int = time.perf_counter_ns()
  try:
    yield
  finally:
    duration_ns: int = time.perf_counter_ns() - start
    duration_ms: float = duration_ns / 1_000_000
    emit(event_type, duration_ms, **context)


@contextmanager
def traced(enter_type: str, exit_type: str, name: str, **context: Any) -> Iterator[None]:
  """
  Context manager to trace entry/exit of a block.

  Example:
      with traced('rule.enter', 'rule.exit', 'expression'):
          parse_expression()

  Args:
      enter_type: Event type for entry
      exit_type: Event type for exit
      name: Name for the traced block
      **context: Additional context

  Raises:
      TypeError: If any string argument is not a string
      ValueError: If any string argument is empty
  """
  # Boundary validation
  for arg_name, arg_value in [("enter_type", enter_type), ("exit_type", exit_type), ("name", name)]:
    if not isinstance(arg_value, str):
      raise TypeError("%s must be str, got %s" % (arg_name, type(arg_value).__name__))
    if not arg_value:
      raise ValueError("%s cannot be empty" % arg_name)

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
