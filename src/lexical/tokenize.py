"""
Lexical analysis framework with integrated observability.

Transforms source text into immutable tokens through pattern-based matching
with support for stateful lexing and position tracking.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Iterator, Any

from .observe import LexicalContext, Position as ObsPosition


# ===== Core Data Structures =====


@dataclass(frozen=True)
class Token:
  """Immutable token with position information."""

  type: str
  value: str
  pos: int
  line: int
  column: int

  @property
  def width(self) -> int:
    return len(self.value)

  @property
  def position(self) -> ObsPosition:
    """Convert to Position object for observability."""
    return ObsPosition(line=self.line, column=self.column, offset=self.pos)


@dataclass
class Match:
  """Result of pattern matching."""

  value: str
  length: int


class LexError(Exception):
  """Lexical analysis error with position context."""

  def __init__(self, message: str, line: int, column: int, source: Optional[str] = None):
    self.line = line
    self.column = column

    location = f" at line {line}, column {column}"
    error_msg = f"{message}{location}"

    if source:
      lines = source.split("\n")
      if 0 <= line - 1 < len(lines):
        line_text = lines[line - 1]
        pointer = " " * (column - 1) + "^"
        error_msg += f"\n{line_text}\n{pointer}"

    super().__init__(error_msg)


class Position:
  """Mutable position tracker for lexing."""

  def __init__(self, text: str):
    self.text = text
    self.pos = 0
    self.line = 1
    self.column = 1

  def advance(self, count: int = 1):
    """Move position forward."""
    for _ in range(count):
      if self.pos < len(self.text):
        if self.text[self.pos] == "\n":
          self.line += 1
          self.column = 1
        else:
          self.column += 1
        self.pos += 1

  def peek(self, offset: int = 0) -> Optional[str]:
    """Look ahead without advancing."""
    idx = self.pos + offset
    return self.text[idx] if idx < len(self.text) else None

  @property
  def at_end(self) -> bool:
    return self.pos >= len(self.text)

  @property
  def at_line_start(self) -> bool:
    return self.column == 1

  def match_literal(self, literal: str) -> bool:
    """Check if literal matches at current position."""
    end = self.pos + len(literal)
    return self.text[self.pos : end] == literal

  def to_obs_position(self) -> ObsPosition:
    """Convert to observability Position."""
    return ObsPosition(line=self.line, column=self.column, offset=self.pos)


# ===== Pattern System =====


@dataclass
class Pattern:
  """Token pattern definition."""

  name: str = ""
  matcher: Optional[Callable[[Position], Optional[Match]]] = None
  skip: bool = False
  at_line_start: bool = False
  when: Optional[Callable] = None
  priority: int = 0


class PatternNamespace:
  """Factory for pattern creation."""

  @staticmethod
  def regex(
    regex_str: str, skip: bool = False, priority: int = 0, at_line_start: bool = False, when: Optional[Callable] = None
  ) -> Pattern:
    """Create regex-based pattern."""
    compiled = re.compile(regex_str)

    def matcher(pos: Position) -> Optional[Match]:
      if m := compiled.match(pos.text, pos.pos):
        return Match(m.group(0), len(m.group(0)))
      return None

    return Pattern(matcher=matcher, skip=skip, priority=priority, at_line_start=at_line_start, when=when)

  @staticmethod
  def literal(
    text: str, skip: bool = False, priority: int = 0, at_line_start: bool = False, when: Optional[Callable] = None
  ) -> Pattern:
    """Create literal text pattern."""

    def matcher(pos: Position) -> Optional[Match]:
      if pos.match_literal(text):
        return Match(text, len(text))
      return None

    return Pattern(matcher=matcher, skip=skip, priority=priority, at_line_start=at_line_start, when=when)

  @staticmethod
  def method(method: Callable) -> Pattern:
    """Create pattern from method."""

    def matcher(lexer_instance, pos: Position) -> Optional[Match]:
      start_pos = pos.pos
      if method(lexer_instance, pos):
        length = pos.pos - start_pos
        value = pos.text[start_pos : pos.pos]
        return Match(value, length)
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

  value: Any = None
  initial: Any = field(init=False)

  def __post_init__(self):
    self.initial = self.value

  def set(self, value: Any):
    self.value = value

  def reset(self):
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

  value: List[Any] = field(default_factory=list)

  def push(self, item: Any):
    self.value.append(item)

  def pop(self) -> Any:
    return self.value.pop() if self.value else None

  @property
  def current(self) -> Any:
    return self.value[-1] if self.value else None

  @property
  def depth(self) -> int:
    return len(self.value)


# ===== Method Pattern Decorator =====


def token(priority: int = 0, skip: bool = False, at_line_start: bool = False, when: Optional[Callable] = None):
  """Decorator for method-based patterns."""

  def decorator(method):
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

  def __init_subclass__(cls):
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
          matcher=(lambda pos, p=pattern: p.matcher(self, pos)) if pattern.matcher else None,
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
    if text and not text.endswith("\n"):
      text += "\n"

    pos = Position(text)

    # Emit lexing start event
    self._obs.emit_event("lex.start", source_length=len(text))

    try:
      while not pos.at_end:
        token = self._next_token(pos)
        if token:
          yield token

      # EOF token
      eof_token = Token("EOF", "", pos.pos, pos.line, pos.column)
      self._obs.emit_token("EOF", "", pos.to_obs_position())
      yield eof_token

    except Exception as e:
      self._obs.emit_error(str(e), pos.to_obs_position())
      if isinstance(e, LexError):
        raise
      raise LexError(str(e), pos.line, pos.column, text)
    finally:
      self._obs.emit_event("lex.complete")

  def _next_token(self, pos: Position) -> Optional[Token]:
    """
    Find and consume next token with observation.

    Emits search start, token, and error events as appropriate.
    """
    if pos.at_end:
      return None

    # Emit search event
    self._obs.emit_search_start(pos.to_obs_position())

    for pattern in self._bound_patterns:
      if pattern.at_line_start and not pos.at_line_start:
        continue

      if pattern.when and not pattern.when(self):
        continue

      if match := pattern.matcher(pos):
        token = Token(pattern.name, match.value, pos.pos, pos.line, pos.column)
        pos.advance(match.length)

        # Emit token event
        self._obs.emit_token(pattern.name, match.value, token.position)

        if not pattern.skip:
          return token

        # Skip token, try next
        return self._next_token(pos)

    # No pattern matched
    char = pos.peek() or "<EOF>"
    error_msg = f"Unexpected character '{char}'"
    self._obs.emit_error(error_msg, pos.to_obs_position())
    raise LexError(error_msg, pos.line, pos.column, pos.text)

  def set_state(self, state_name: str, value: Any) -> None:
    """
    Set lexer state with observation.

    Emits state change events for debugging and analysis.
    """
    if hasattr(self, state_name):
      old_value = getattr(self, state_name)
      setattr(self, state_name, value)
      self._obs.state_change(state_name, old_value, value)
