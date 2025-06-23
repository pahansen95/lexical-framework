"""
Unified position tracking for lexical analysis.

Provides immutable position representation and efficient navigation
for source text processing. All position tracking in the framework
flows through this module.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class Position:
  """
  Immutable position in source text.

  Represents a specific location with line, column, and offset information.
  All position objects are immutable to ensure thread safety and enable
  structural sharing in syntax trees.
  """

  line: int = 1
  column: int = 1
  offset: int = 0

  def __post_init__(self) -> None:
    """Validate position invariants."""
    if self.line < 1:
      raise ValueError(f"Line must be >= 1, got {self.line}")
    if self.column < 1:
      raise ValueError(f"Column must be >= 1, got {self.column}")
    if self.offset < 0:
      raise ValueError(f"Offset must be >= 0, got {self.offset}")

  def with_offset(self, new_offset: int) -> "Position":
    """
    Create new position with updated offset.

    For simple same-line offset updates. Does not handle
    line boundary crossing.
    """
    if new_offset == self.offset:
      return self
    if new_offset > self.offset:
      column_delta = new_offset - self.offset
      return Position(self.line, self.column + column_delta, new_offset)
    raise ValueError("Cannot move position backwards with with_offset")


@dataclass(frozen=True, slots=True)
class PositionRange:
  """
  Range between two positions in source text.

  Represents a span of text with start and end positions.
  Useful for error reporting and source mapping.
  """

  start: Position
  end: Position

  def __post_init__(self) -> None:
    """Validate range invariants."""
    if self.start.offset > self.end.offset:
      raise ValueError(f"Invalid range: start offset {self.start.offset} > end offset {self.end.offset}")

  @property
  def is_empty(self) -> bool:
    """Check if range has zero width."""
    return self.start.offset == self.end.offset

  def contains_offset(self, offset: int) -> bool:
    """Check if offset falls within range."""
    return self.start.offset <= offset < self.end.offset

  def contains_position(self, pos: Position) -> bool:
    """Check if position falls within range."""
    return self.contains_offset(pos.offset)


class SourceNavigator:
  """
  Efficient navigation through source text with position tracking.

  Provides mutable navigation for lexing while producing immutable
  Position objects for external use. Handles line/column tracking
  automatically during navigation.
  """

  __slots__ = ("_text", "_pos", "_line", "_column", "_length")

  def __init__(self, text: str):
    """
    Initialize navigator at start of text.

    Args:
        text: Source text to navigate
    """
    self._text = text
    self._pos = 0
    self._line = 1
    self._column = 1
    self._length = len(text)

  @property
  def position(self) -> Position:
    """Get current position as immutable object."""
    return Position(self._line, self._column, self._pos)

  @property
  def at_end(self) -> bool:
    """Check if at end of source."""
    return self._pos >= self._length

  @property
  def at_line_start(self) -> bool:
    """Check if at start of line."""
    return self._column == 1

  @property
  def offset(self) -> int:
    """Current offset in source."""
    return self._pos

  def advance(self, count: int = 1) -> Position:
    """
    Advance position and return new Position object.

    Updates internal state and returns the position after advancing.
    Handles line/column tracking for newline characters.

    Args:
        count: Number of characters to advance

    Returns:
        Position after advancing
    """
    for _ in range(count):
      if self._pos < self._length:
        if self._text[self._pos] == "\n":
          self._line += 1
          self._column = 1
        else:
          self._column += 1
        self._pos += 1

    return self.position

  def peek(self, offset: int = 0) -> Optional[str]:
    """
    Look ahead without advancing.

    Args:
        offset: Number of characters to look ahead

    Returns:
        Character at offset or None if beyond end
    """
    idx = self._pos + offset
    return self._text[idx] if idx < self._length else None

  def peek_many(self, count: int) -> str:
    """
    Look ahead at multiple characters.

    Args:
        count: Number of characters to peek

    Returns:
        String of characters or partial string if at end
    """
    start = self._pos
    end = min(start + count, self._length)
    return self._text[start:end]

  def match_literal(self, literal: str) -> bool:
    """
    Check if literal matches at current position.

    Args:
        literal: String to match

    Returns:
        True if literal matches at current position
    """
    end = self._pos + len(literal)
    if end > self._length:
      return False
    return self._text[self._pos : end] == literal

  def consume_literal(self, literal: str) -> Optional[Position]:
    """
    Consume literal if it matches, returning position after.

    Args:
        literal: String to consume

    Returns:
        Position after literal or None if no match
    """
    if self.match_literal(literal):
      return self.advance(len(literal))
    return None

  def save_state(self) -> tuple[int, int, int]:
    """
    Save current navigation state.

    Returns:
        Tuple of (offset, line, column) for restoration
    """
    return (self._pos, self._line, self._column)

  def restore_state(self, state: tuple[int, int, int]) -> None:
    """
    Restore saved navigation state.

    Args:
        state: Previously saved state tuple
    """
    self._pos, self._line, self._column = state

  def remaining_text(self) -> str:
    """Get text from current position to end."""
    return self._text[self._pos :]

  def text_at(self, start: int, end: int) -> str:
    """
    Get text between offsets.

    Args:
        start: Start offset
        end: End offset

    Returns:
        Text slice between offsets
    """
    return self._text[start:end]
