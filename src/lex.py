"""
Simplified Lexer Framework

A declarative framework for building lexical analyzers with clear pattern
definitions and straightforward state management.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Iterator, Any


# ===== Core Data Structures =====


@dataclass
class Token:
  """Represents a lexical token with position information."""

  type: str
  value: str
  pos: int
  line: int
  column: int

  def __repr__(self):
    return f"Token({self.type}, {repr(self.value)}, {self.line}:{self.column})"


@dataclass
class Match:
  """Result of a pattern match."""

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


# ===== Position Tracking =====


class Position:
  """Tracks position in source text."""

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
    """Check if at end of input."""
    return self.pos >= len(self.text)

  @property
  def at_line_start(self) -> bool:
    """Check if at start of line."""
    return self.column == 1

  def match_regex(self, pattern: re.Pattern) -> Optional[Match]:
    """Try to match regex at current position."""
    if match := pattern.match(self.text, self.pos):
      return Match(match.group(0), match.end() - match.start())
    return None

  def match_literal(self, text: str) -> Optional[Match]:
    """Try to match literal text."""
    if self.text[self.pos :].startswith(text):
      return Match(text, len(text))
    return None


# ===== Pattern Definition =====


@dataclass
class Pattern:
  """Defines a token pattern."""

  name: str
  matcher: Callable[[Position], Optional[Match]]
  priority: int = 0
  skip: bool = False
  when: Optional[Callable[[Any], bool]] = None
  at_line_start: bool = False


class PatternBuilder:
  """Builder for creating patterns."""

  @staticmethod
  def regex(pattern: str, **kwargs) -> Pattern:
    """Create regex-based pattern."""
    compiled = re.compile(pattern)
    return Pattern(name="", matcher=lambda pos: pos.match_regex(compiled), **kwargs)

  @staticmethod
  def literal(text: str, **kwargs) -> Pattern:
    """Create literal pattern."""
    return Pattern(name="", matcher=lambda pos: pos.match_literal(text), **kwargs)

  @staticmethod
  def method(fn: Callable) -> Pattern:
    """Create method-based pattern."""

    def matcher(pos: Position) -> Optional[Match]:
      # Mark position for potential backtrack
      start_pos = pos.pos
      start_line = pos.line
      start_col = pos.column

      # Call method with position
      if fn(pos):
        length = pos.pos - start_pos
        value = pos.text[start_pos : pos.pos]
        return Match(value, length)
      else:
        # Restore position on failure
        pos.pos = start_pos
        pos.line = start_line
        pos.column = start_col
        return None

    return Pattern(name=fn.__name__, matcher=matcher, **getattr(fn, "_pattern_kwargs", {}))


# Pattern builder instance
pattern = PatternBuilder()


# ===== Decorators =====


def token(**kwargs):
  """Decorator for method-based token patterns."""

  def decorator(fn):
    fn._pattern_kwargs = kwargs
    return fn

  return decorator


# ===== State Management =====


@dataclass
class State:
  """Simple state container."""

  value: Any
  initial: Any = field(init=False)

  def __post_init__(self):
    self.initial = self.value

  def set(self, value: Any):
    """Update state value."""
    self.value = value

  def reset(self):
    """Reset to initial value."""
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


# ===== Lexer Base Class =====


class Lexer:
  """Base class for lexical analyzers."""

  def __init_subclass__(cls):
    """Collect patterns from class definition."""
    cls._patterns = []
    cls._states = {}

    for name, value in cls.__dict__.items():
      if isinstance(value, Pattern):
        value.name = value.name or name
        cls._patterns.append(value)
      elif hasattr(value, "_pattern_kwargs"):
        # Method-based pattern
        pattern_obj = pattern.method(value)
        pattern_obj.name = name
        cls._patterns.append(pattern_obj)
      elif isinstance(value, State):
        cls._states[name] = value

    # Sort by priority (highest first)
    cls._patterns.sort(key=lambda p: p.priority, reverse=True)

  def __init__(self):
    """Initialize lexer instance."""
    # Create instance copies of states
    for name, template in self._states.items():
      state_copy = type(template)(template.value)
      setattr(self, name, state_copy)

  def lex(self, text: str) -> Iterator[Token]:
    """Tokenize input text."""
    # Ensure text ends with newline
    if text and not text.endswith("\n"):
      text += "\n"

    pos = Position(text)

    try:
      while not pos.at_end:
        token = self._next_token(pos)
        if token:
          yield token

      # Generate end marker
      yield Token("EOF", "", pos.pos, pos.line, pos.column)

    except Exception as e:
      if isinstance(e, LexError):
        raise
      raise LexError(str(e), pos.line, pos.column, text)

  def _next_token(self, pos: Position) -> Optional[Token]:
    """Find and consume next token."""
    for pattern in self._patterns:
      # Check conditions
      if pattern.at_line_start and not pos.at_line_start:
        continue

      if pattern.when and not pattern.when(self):
        continue

      # Try to match
      if match := pattern.matcher(pos):
        # Create token
        token = Token(pattern.name, match.value, pos.pos, pos.line, pos.column)

        # Advance position
        pos.advance(match.length)

        # Return token unless skip
        if not pattern.skip:
          return token

        # For skip tokens, continue to next
        return self._next_token(pos)

    # No match found
    char = pos.peek()
    raise LexError(f"Unexpected character '{char}'", pos.line, pos.column, pos.text)
