"""
Lexical analysis framework with integrated observability.

Transforms source text into immutable tokens through pattern-based matching
with support for stateful lexing and position tracking.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Iterator, Union

from .observe import LexicalContext
from .position import Position, SourceNavigator


# ===== Core Data Structures =====

# Type alias for allowed state values
StateValue = Union[int, str, bool, List[str], None]


@dataclass(frozen=True)
class Token:
  """Immutable token with position information."""

  type: str
  value: str
  position: Position

  @property
  def width(self) -> int:
    return len(self.value)

  # Compatibility properties for existing code
  @property
  def pos(self) -> int:
    return self.position.offset

  @property
  def line(self) -> int:
    return self.position.line

  @property
  def column(self) -> int:
    return self.position.column


@dataclass
class Match:
  """Result of pattern matching."""

  value: str
  length: int


class LexError(Exception):
  """Lexical analysis error with position context."""

  def __init__(self, message: str, position: Position, source: Optional[str] = None):
    self.position = position
    self.line = position.line
    self.column = position.column

    location = f" at line {position.line}, column {position.column}"
    error_msg = f"{message}{location}"

    if source:
      lines = source.split("\n")
      if 0 <= position.line - 1 < len(lines):
        line_text = lines[position.line - 1]
        pointer = " " * (position.column - 1) + "^"
        error_msg += f"\n{line_text}\n{pointer}"

    super().__init__(error_msg)


# ===== Pattern System =====


@dataclass
class Pattern:
  """Token pattern definition."""

  name: str = ""
  matcher: Optional[Callable[[SourceNavigator], Optional[Match]]] = None
  skip: bool = False
  at_line_start: bool = False
  when: Optional[Callable[["Lexer"], bool]] = None
  priority: int = 0


class PatternNamespace:
  """Factory for pattern creation."""

  @staticmethod
  def _static_matcher(
    func: Callable[[SourceNavigator], Optional[Match]],
  ) -> Callable[["Lexer", SourceNavigator], Optional[Match]]:
    """Wrap static matchers to accept lexer argument for uniform interface."""

    def wrapper(lexer: "Lexer", nav: SourceNavigator) -> Optional[Match]:
      return func(nav)

    return wrapper

  @staticmethod
  def regex(
    regex_str: str,
    skip: bool = False,
    priority: int = 0,
    at_line_start: bool = False,
    when: Optional[Callable[["Lexer"], bool]] = None,
  ) -> Pattern:
    """Create regex-based pattern."""
    compiled = re.compile(regex_str)

    def matcher(nav: SourceNavigator) -> Optional[Match]:
      remaining = nav.remaining_text()
      if m := compiled.match(remaining):
        return Match(m.group(0), len(m.group(0)))
      return None

    return Pattern(
      matcher=PatternNamespace._static_matcher(matcher),
      skip=skip,
      priority=priority,
      at_line_start=at_line_start,
      when=when,
    )

  @staticmethod
  def literal(
    text: str,
    skip: bool = False,
    priority: int = 0,
    at_line_start: bool = False,
    when: Optional[Callable[["Lexer"], bool]] = None,
  ) -> Pattern:
    """Create literal text pattern."""

    def matcher(nav: SourceNavigator) -> Optional[Match]:
      if nav.match_literal(text):
        return Match(text, len(text))
      return None

    return Pattern(
      matcher=PatternNamespace._static_matcher(matcher),
      skip=skip,
      priority=priority,
      at_line_start=at_line_start,
      when=when,
    )

  @staticmethod
  def method(method: Callable[["Lexer", SourceNavigator], Optional[Match]]) -> Pattern:
    """Create pattern from method."""

    def matcher(lexer_instance: "Lexer", nav: SourceNavigator) -> Optional[Match]:
      start_pos = nav.offset
      result = method(lexer_instance, nav)
      if result and result.length > 0:
        return result
      # Reset if no match
      if nav.offset != start_pos:
        nav.restore_state((start_pos, nav._line, nav._column))
      return None

    return Pattern(
      matcher=matcher,
      skip=getattr(method, "_skip", False),
      priority=getattr(method, "_priority", 0),
      at_line_start=getattr(method, "_at_line_start", False),
      when=getattr(method, "_when", None),
    )


pattern = PatternNamespace()


# ===== State Management =====


@dataclass
class State:
  """Generic mutable state container."""

  value: StateValue = None
  initial: StateValue = field(init=False)

  def __post_init__(self) -> None:
    self.initial = self.value

  def set(self, value: StateValue) -> None:
    self.value = value

  def reset(self) -> None:
    self.value = self.initial


@dataclass
class Counter(State):
  """Counter state for numeric values."""

  value: int = 0

  def increment(self, amount: int = 1) -> int:
    self.value += amount
    return self.value

  def decrement(self, amount: int = 1) -> int:
    self.value -= amount
    return self.value


@dataclass
class Stack(State):
  """Stack state for nested contexts."""

  value: List[StateValue] = field(default_factory=list)

  def push(self, item: StateValue) -> None:
    self.value.append(item)

  def pop(self) -> StateValue:
    return self.value.pop() if self.value else None

  @property
  def current(self) -> StateValue:
    return self.value[-1] if self.value else None

  @property
  def depth(self) -> int:
    return len(self.value)


# ===== Method Pattern Decorator =====


def token(
  priority: int = 0, skip: bool = False, at_line_start: bool = False, when: Optional[Callable[["Lexer"], bool]] = None
):
  """Decorator for method-based patterns."""

  def decorator(
    method: Callable[["Lexer", SourceNavigator], Optional[Match]],
  ) -> Callable[["Lexer", SourceNavigator], Optional[Match]]:
    method._pattern_kwargs = True
    method._priority = priority
    method._skip = skip
    method._at_line_start = at_line_start
    method._when = when
    return method

  return decorator


# ===== Lexer Base Class =====


class Lexer:
  """
  Base class for lexical analyzers with integrated observability.

  Uses __init_subclass__ for declarative pattern collection from
  class attributes and decorated methods.
  """

  def __init_subclass__(cls) -> None:
    """Collect patterns from class definition."""
    cls._patterns = []
    cls._states = {}

    for name, value in cls.__dict__.items():
      if isinstance(value, Pattern):
        value.name = value.name or name
        cls._patterns.append(value)
      elif hasattr(value, "_pattern_kwargs"):
        pattern_obj = pattern.method(value)
        pattern_obj.name = name
        cls._patterns.append(pattern_obj)
      elif isinstance(value, State):
        cls._states[name] = value

    cls._patterns.sort(key=lambda p: p.priority, reverse=True)

  def __init__(self, obs_context: Optional[LexicalContext] = None):
    """
    Initialize lexer with observability.

    Args:
        obs_context: Observability context or None for null context
    """
    # Initialize observability first
    self._obs = obs_context or LexicalContext.null()

    # Copy state templates
    for name, template in self._states.items():
      state_copy = type(template)(template.value)
      setattr(self, name, state_copy)

    # Bind method patterns to this instance
    self._bound_patterns = []
    for pattern in self._patterns:
      if hasattr(pattern.matcher, "__self__"):
        # Already bound (shouldn't happen)
        self._bound_patterns.append(pattern)
      else:
        # Create bound version
        bound_pattern = Pattern(
          name=pattern.name,
          matcher=(lambda nav, p=pattern: p.matcher(self, nav)) if pattern.matcher else None,
          skip=pattern.skip,
          priority=pattern.priority,
          at_line_start=pattern.at_line_start,
          when=pattern.when,
        )
        self._bound_patterns.append(bound_pattern)

  def lex(self, text: str) -> Iterator[Token]:
    """
    Tokenize input text with automatic observation.

    Emits lex.start and lex.complete events, plus individual
    token events as patterns match.
    """
    # Boundary validation
    assert isinstance(text, str), f"text must be str, got {type(text).__name__}"

    if text and not text.endswith("\n"):
      text += "\n"

    nav = SourceNavigator(text)

    # Emit lexing start event
    self._obs.emit_event("lex.start", source_length=len(text))

    try:
      while not nav.at_end:
        token = self._next_token(nav)
        if token:
          yield token

      # EOF token
      eof_token = Token("EOF", "", nav.position)
      self._obs.emit_token("EOF", "", nav.position)
      yield eof_token

    except Exception as e:
      self._obs.emit_error(str(e), nav.position)
      if isinstance(e, LexError):
        raise
      raise LexError(str(e), nav.position, text)
    finally:
      self._obs.emit_event("lex.complete")

  def _next_token(self, nav: SourceNavigator) -> Optional[Token]:
    """
    Find and consume next token with observation.

    Emits search start, token, and error events as appropriate.
    """
    if nav.at_end:
      return None

    # Emit search event
    self._obs.emit_search_start(nav.position)

    # Save position before matching
    start_pos = nav.position

    for pattern in self._bound_patterns:
      if pattern.at_line_start and not nav.at_line_start:
        continue

      if pattern.when and not pattern.when(self):
        continue

      if match := pattern.matcher(nav):
        # Create token with start position
        token = Token(pattern.name, match.value, start_pos)

        # Advance navigator
        nav.advance(match.length)

        # Emit token event
        self._obs.emit_token(pattern.name, match.value, start_pos)

        if not pattern.skip:
          return token

        # Skip token, try next
        return self._next_token(nav)

    # No pattern matched
    char = nav.peek() or "<EOF>"
    error_msg = f"Unexpected character '{char}'"
    self._obs.emit_error(error_msg, nav.position)
    raise LexError(error_msg, nav.position, nav._text)

  def set_state(self, state_name: str, value: StateValue) -> None:
    """
    Set lexer state with observation.

    Emits state change events for debugging and analysis.
    """
    # Boundary validation
    assert hasattr(self, state_name), f"Unknown state: {state_name}"
    assert isinstance(value, (int, str, bool, list, type(None))), f"Invalid state value type: {type(value).__name__}"

    old_value = getattr(self, state_name)
    assert hasattr(old_value, "set"), f"{state_name} is not a mutable state"

    # Set new value
    old_value.set(value)
    self._obs.state_change(state_name, old_value.value, value)
