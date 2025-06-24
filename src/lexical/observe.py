"""
Lexical observability domain for parsing and lexing operations.

Provides specialized event emission for lexical analysis with automatic
parse context tracking and zero overhead when disabled.

Core Components:
- Parse stack management for automatic context
- Event emission for tokens, rules, and AST nodes
- Source fragment extraction for debugging
- Zero-overhead design when no handlers attached
- Null object pattern for disabled observability

Design Principles:
- Progressive disclosure (simple defaults, advanced options)
- Lazy computation (work only when observing)
- Explicit dependencies (no hidden state)
- Industry-standard terminology
"""

import threading
import time
from contextlib import contextmanager, nullcontext
from typing import Any, Optional, ContextManager
from collections.abc import Mapping
from observability import ObservabilityContext, SharedContext

# Import unified Position from position module
from .position import Position

# Event type constants prevent runtime string construction
# Lexer events
LEX_TOKEN_EMIT = "lex.token.emit"
LEX_STATE_TRANSITION = "lex.state.transition"
LEX_BUFFER_OPERATION = "lex.buffer.operation"
LEX_ERROR_RECOVERY = "lex.error.recovery"

# Parser events
PARSE_RULE_ENTER = "parse.rule.enter"
PARSE_RULE_EXIT = "parse.rule.exit"
PARSE_BACKTRACK = "parse.backtrack"
PARSE_CACHE_HIT = "parse.cache.hit"
PARSE_CACHE_MISS = "parse.cache.miss"

# AST events
AST_NODE_CREATE = "ast.node.create"
AST_TRANSFORM_APPLY = "ast.transform.apply"
AST_VALIDATION_CHECK = "ast.validation.check"


class SpanIdGenerator:
  """Thread-safe unique span ID generator."""

  _instance: Optional["SpanIdGenerator"] = None
  _lock = threading.Lock()

  def __new__(cls) -> "SpanIdGenerator":
    if cls._instance is None:
      with cls._lock:
        if cls._instance is None:
          cls._instance = super().__new__(cls)
          cls._instance._counter = 0
          cls._instance._counter_lock = threading.Lock()
    return cls._instance

  def next_id(self) -> str:
    """Generate next unique span ID."""
    with self._counter_lock:
      self._counter += 1
      return f"{self._counter:x}"

  def reset(self) -> None:
    """Reset counter for testing."""
    with self._counter_lock:
      self._counter = 0


# Module-level instance
_span_id_generator = SpanIdGenerator()


def _generate_span_id() -> str:
  """Generate unique span ID efficiently."""
  return _span_id_generator.next_id()


class NullLexicalContext:
  """
  No-op implementation for disabled observability.

  Provides zero-overhead observability operations when no handlers
  are attached. All methods are minimal no-ops to ensure the fastest
  possible execution path.
  """

  def has_handlers(self) -> bool:
    """Always returns False for null context."""
    return False

  def emit_token(self, token_type: str, value: str, position: Optional[Position] = None) -> None:
    """No-op token emission."""
    pass

  def emit_search_start(self, position: Position) -> None:
    """No-op search start event."""
    pass

  def emit_backtrack(self, rule: str, reason: str) -> None:
    """No-op backtrack event."""
    pass

  def emit_error(self, message: str, position: Optional[Position] = None) -> None:
    """No-op error event."""
    pass

  def emit_event(self, event_type: str, value: Any = None, **metadata: Any) -> None:
    """No-op generic event emission."""
    pass

  def rule(self, name: str, position: Optional[Position] = None) -> ContextManager[None]:
    """Return null context manager for rule tracking."""
    return nullcontext()

  def state_change(self, state_name: str, old_value: Any, new_value: Any) -> None:
    """No-op state change event."""
    pass

  def emit_state_transition(self, from_state: str, to_state: str) -> None:
    """No-op state transition event."""
    pass

  def emit_ast_node(self, node_type: str, attributes: Mapping[str, Any], position: Optional[Position] = None) -> None:
    """No-op AST node event."""
    pass


# Singleton null context for zero allocation overhead
_null_context = NullLexicalContext()


class LexicalContext:
  """
  Observability context for lexical analysis operations.

  Maintains parse stack and emits structured events with
  automatic context enrichment. Designed for zero overhead
  when observability is disabled.

  Args:
      observability_context: Parent observability context
      source: Optional source text for fragment extraction
      max_depth: Stack overflow protection limit (default 1000)
      fragment_window: Source context window size (default 40)
      thread_safe: Enable thread-local parse stacks (default True)
      capture_errors: Enable rich error context (default True)
  """

  def __init__(
    self,
    observability_context: Optional[ObservabilityContext] = None,
    source: Optional[str] = None,
    max_depth: int = 1000,
    fragment_window: int = 40,
    thread_safe: bool = True,
    capture_errors: bool = True,
  ) -> None:
    if observability_context is None:
      self._context = SharedContext.get()
    else:
      self._context = observability_context
    self._source = source
    self._max_depth = max_depth
    self._fragment_window = fragment_window
    self._capture_errors = capture_errors

    # Thread-local storage for parse stacks
    if thread_safe:
      self._local = threading.local()
    else:
      # Lightweight object for single-threaded mode
      self._local = type("LocalStorage", (), {"parse_stack": [], "rule_timings": []})()

  @staticmethod
  def null() -> NullLexicalContext:
    """Return singleton null context for zero-overhead operation."""
    return _null_context

  @property
  def _parse_stack(self) -> list[str]:
    """Access thread-local parse stack."""
    if not hasattr(self._local, "parse_stack"):
      self._local.parse_stack = []
    return self._local.parse_stack

  @property
  def _rule_timings(self) -> list[int]:
    """Access thread-local timing stack."""
    if not hasattr(self._local, "rule_timings"):
      self._local.rule_timings = []
    return self._local.rule_timings

  def has_handlers(self) -> bool:
    """Check if any handlers are attached."""
    return self._context.has_handlers()

  @contextmanager
  def rule(self, name: str, position: Optional[Position] = None):
    """
    Context manager for parser rule tracking.

    Automatically maintains parse stack and emits enter/exit
    events with timing information.

    Args:
        name: Rule name for stack tracking
        position: Optional source position

    Raises:
        RecursionError: When parse depth exceeds max_depth
    """
    # Fast path - no handlers
    if not self._context.has_handlers():
      yield
      return

    # Check depth limit
    stack = self._parse_stack
    if len(stack) >= self._max_depth:
      raise RecursionError(
        f"Parse depth limit ({self._max_depth}) exceeded at rule '{name}'. "
        f"Current stack: {' > '.join(stack[-5:])}... "
        f"Consider increasing max_depth or checking for infinite recursion."
      )

    # Enter rule
    stack.append(name)
    enter_time = time.perf_counter_ns()
    self._rule_timings.append(enter_time)

    # Generate span ID using singleton
    span_id = _generate_span_id()

    # Lazy metadata construction
    metadata = {"rule": name, "parse_stack": list(stack), "parse_depth": len(stack), "span_id": span_id}
    if position is not None:
      metadata["position"] = position

    self._context.emit(PARSE_RULE_ENTER, name, **metadata)

    try:
      yield
    finally:
      # Exit rule
      stack.pop()
      start_time = self._rule_timings.pop()
      duration_ns = time.perf_counter_ns() - start_time

      metadata = {
        "rule": name,
        "parse_stack": list(stack),
        "parse_depth": len(stack),
        "duration_ns": duration_ns,
        "duration_ms": duration_ns / 1_000_000,
        "span_id": span_id,
      }

      self._context.emit(PARSE_RULE_EXIT, name, **metadata)

  def emit_token(self, token_type: str, value: str, position: Optional[Position] = None) -> None:
    """
    Emit token event with automatic context enrichment.

    Args:
        token_type: Token classification (e.g., 'NUMBER', 'IDENTIFIER')
        value: Token text value
        position: Optional source position (unified Position type)
    """
    if not self._context.has_handlers():
      return

    stack = self._parse_stack
    metadata = {"token_type": token_type, "token_value": value}

    # Only add context if present
    if stack:
      metadata["parse_stack"] = list(stack)
      metadata["parse_depth"] = len(stack)

    if position is not None:
      metadata["position"] = position
      if self._source:
        fragment = self._extract_fragment(position)
        if fragment:
          metadata["source_fragment"] = fragment

    self._context.emit(LEX_TOKEN_EMIT, value, **metadata)

  def emit_search_start(self, position: Position) -> None:
    """
    Emit token search start event.

    Args:
        position: Current position in source (unified Position type)
    """
    if not self._context.has_handlers():
      return

    metadata = {"position": position}
    self._context.emit("lex.search.start", None, **metadata)

  def emit_backtrack(self, rule: str, reason: str) -> None:
    """
    Emit parser backtrack event.

    Args:
        rule: Rule that triggered backtrack
        reason: Human-readable backtrack reason
    """
    if not self._context.has_handlers():
      return

    stack = self._parse_stack
    metadata = {"rule": rule, "reason": reason}

    if stack:
      metadata["parse_stack"] = list(stack)
      metadata["parse_depth"] = len(stack)

    self._context.emit(PARSE_BACKTRACK, reason, **metadata)

  def emit_error(self, message: str, position: Optional[Position] = None) -> None:
    """
    Emit error event with context.

    Args:
        message: Error message
        position: Optional error position (unified Position type)
    """
    if not self._context.has_handlers():
      return

    metadata = {"error": message}
    if position:
      metadata["position"] = position

    self._context.emit("error", message, **metadata)

  def emit_event(self, event_type: str, value: Any = None, **metadata: Any) -> None:
    """
    Emit generic event.

    Args:
        event_type: Event classification
        value: Event value
        **metadata: Additional event metadata
    """
    if not self._context.has_handlers():
      return

    self._context.emit(event_type, value, **metadata)

  def emit_ast_node(self, node_type: str, attributes: Mapping[str, Any], position: Optional[Position] = None) -> None:
    """
    Emit AST node creation event.

    Args:
        node_type: AST node classification
        attributes: Node attributes/properties
        position: Optional source position (unified Position type)
    """
    if not self._context.has_handlers():
      return

    stack = self._parse_stack
    metadata = {"node_type": node_type, "attributes": dict(attributes)}

    if stack:
      metadata["parse_stack"] = list(stack)
      metadata["parse_depth"] = len(stack)

    if position is not None:
      metadata["position"] = position

    self._context.emit(AST_NODE_CREATE, node_type, **metadata)

  def emit_state_transition(self, from_state: str, to_state: str) -> None:
    """
    Emit lexer state transition event.

    Args:
        from_state: Previous lexer state
        to_state: New lexer state
    """
    if not self._context.has_handlers():
      return

    metadata = {"from_state": from_state, "to_state": to_state}

    stack = self._parse_stack
    if stack:
      metadata["parse_stack"] = list(stack)
      metadata["parse_depth"] = len(stack)

    value = f"{from_state} -> {to_state}"
    self._context.emit(LEX_STATE_TRANSITION, value, **metadata)

  def state_change(self, state_name: str, old_value: Any, new_value: Any) -> None:
    """
    Emit state change event.

    Args:
        state_name: Name of state variable
        old_value: Previous value
        new_value: New value
    """
    if not self._context.has_handlers():
      return

    metadata = {"state_name": state_name, "old_value": old_value, "new_value": new_value}

    self._context.emit("state.change", state_name, **metadata)

  def _extract_fragment(self, position: Position) -> str:
    """
    Extract source fragment around position.

    Returns contextual window with position marker or
    line boundaries, whichever provides better context.

    Args:
        position: Source position for fragment center (unified Position type)

    Returns:
        Formatted source fragment with ellipsis markers
    """
    if not self._source or position is None:
      return ""

    source_len = len(self._source)
    if position.offset >= source_len:
      return ""

    # Calculate initial boundaries
    start = max(0, position.offset - self._fragment_window)
    end = min(source_len, position.offset + self._fragment_window)

    # Extend to token boundaries for readability
    # Use memoryview to avoid string copies
    source_view = memoryview(self._source.encode("utf-8"))

    # Extend start to token boundary
    while start > 0:
      if source_view[start - 1] in b" \t\n\r":
        break
      start -= 1

    # Extend end to token boundary
    while end < source_len:
      if source_view[end] in b" \t\n\r":
        break
      end += 1

    # Extract fragment
    fragment = self._source[start:end]

    # Format with ellipsis
    if start > 0:
      fragment = "..." + fragment
    if end < source_len:
      fragment = fragment + "..."

    return fragment


# Public API exports
__all__ = [
  # Context classes
  "LexicalContext",
  "NullLexicalContext",
  # Lexer events
  "LEX_TOKEN_EMIT",
  "LEX_STATE_TRANSITION",
  "LEX_BUFFER_OPERATION",
  "LEX_ERROR_RECOVERY",
  # Parser events
  "PARSE_RULE_ENTER",
  "PARSE_RULE_EXIT",
  "PARSE_BACKTRACK",
  "PARSE_CACHE_HIT",
  "PARSE_CACHE_MISS",
  # AST events
  "AST_NODE_CREATE",
  "AST_TRANSFORM_APPLY",
  "AST_VALIDATION_CHECK",
]
