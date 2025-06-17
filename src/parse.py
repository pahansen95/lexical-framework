"""
Simplified Parser Framework

A declarative framework for building recursive descent parsers with automatic
CST construction and clean grammar expression.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Callable, Union
from contextlib import contextmanager


# ===== Core Data Structures =====


@dataclass
class Token:
  """Represents a lexical token."""

  type: str
  value: str
  pos: int
  line: int
  column: int

  def __repr__(self):
    return f"Token({self.type}, {repr(self.value)})"


@dataclass
class Node:
  """Represents a node in the parse tree."""

  type: str
  children: List[Union["Node", Token]] = field(default_factory=list)

  def __repr__(self):
    return f"Node({self.type}, {len(self.children)} children)"


class ParseError(Exception):
  """Raised when parsing fails."""

  pass


# ===== Token Stream =====


class TokenStream:
  """Manages navigation through tokens."""

  def __init__(self, tokens: List[Token]):
    self.tokens = tokens
    self.pos = 0

  def peek(self, offset: int = 0) -> Optional[Token]:
    """Look ahead without consuming."""
    idx = self.pos + offset
    return self.tokens[idx] if idx < len(self.tokens) else None

  def consume(self) -> Token:
    """Consume and return current token."""
    if self.at_end():
      raise ParseError("Unexpected end of input")
    token = self.tokens[self.pos]
    self.pos += 1
    return token

  def match(self, *types: str) -> bool:
    """Check if current token matches types."""
    token = self.peek()
    return token and token.type in types

  def expect(self, *types: str) -> Token:
    """Consume token of expected type."""
    token = self.peek()
    if not token:
      raise ParseError(f"Expected {types} but reached end")
    if token.type not in types:
      raise ParseError(f"Expected {types} but got {token.type} at line {token.line}")
    return self.consume()

  def at_end(self) -> bool:
    """Check if at end of stream."""
    return self.pos >= len(self.tokens)

  def save(self) -> int:
    """Save current position."""
    return self.pos

  def restore(self, pos: int):
    """Restore saved position."""
    self.pos = pos


# ===== Parser Base Class =====


class Parser:
  """Base class for recursive descent parsers."""

  def __init__(self, tokens: List[Token]):
    self.tokens = TokenStream(tokens)
    self.structural_tokens = {"WHITESPACE", "COMMENT", "NEWLINE"}
    self.skip_structural = False

  # ===== Token Operations =====

  def consume(self) -> Token:
    """Consume next token."""
    if self.skip_structural:
      self._skip_structural_tokens()
    return self.tokens.consume()

  def expect(self, *types: str) -> Token:
    """Expect and consume token."""
    if self.skip_structural:
      self._skip_structural_tokens()
    return self.tokens.expect(*types)

  def match(self, *types: str) -> bool:
    """Check if next token matches."""
    if self.skip_structural:
      pos = self.tokens.save()
      self._skip_structural_tokens()
      result = self.tokens.match(*types)
      self.tokens.restore(pos)
      return result
    return self.tokens.match(*types)

  def peek(self) -> Optional[Token]:
    """Look at next token."""
    if self.skip_structural:
      pos = self.tokens.save()
      self._skip_structural_tokens()
      token = self.tokens.peek()
      self.tokens.restore(pos)
      return token
    return self.tokens.peek()

  def _skip_structural_tokens(self):
    """Skip over structural tokens."""
    while self.tokens.match(*self.structural_tokens):
      self.tokens.consume()

  # ===== Parser Combinators =====

  def choice(self, *alternatives: Callable) -> Any:
    """Try alternatives in order."""
    pos = self.tokens.save()
    last_error = None

    for alt in alternatives:
      try:
        return alt()
      except ParseError as e:
        last_error = e
        self.tokens.restore(pos)

    raise last_error or ParseError("No alternatives matched")

  def many(self, parser_fn: Callable) -> List[Any]:
    """Parse zero or more occurrences."""
    results = []
    while True:
      pos = self.tokens.save()
      try:
        results.append(parser_fn())
      except ParseError:
        self.tokens.restore(pos)
        break
    return results

  def some(self, parser_fn: Callable) -> List[Any]:
    """Parse one or more occurrences."""
    results = [parser_fn()]
    results.extend(self.many(parser_fn))
    return results

  def optional(self, parser_fn: Callable) -> Optional[Any]:
    """Parse zero or one occurrence."""
    pos = self.tokens.save()
    try:
      return parser_fn()
    except ParseError:
      self.tokens.restore(pos)
      return None

  def separated(self, parser_fn: Callable, delimiter: str) -> List[Any]:
    """Parse delimited sequence."""
    results = [parser_fn()]
    while self.match(delimiter):
      self.consume()
      results.append(parser_fn())
    return results

  # ===== Context Managers =====

  @contextmanager
  def structural_handling(self, enabled: bool):
    """Temporarily change structural token handling."""
    old_value = self.skip_structural
    self.skip_structural = enabled
    try:
      yield
    finally:
      self.skip_structural = old_value

  @contextmanager
  def custom_structural(self, tokens: set):
    """Temporarily use custom structural tokens."""
    old_tokens = self.structural_tokens
    self.structural_tokens = tokens
    try:
      yield
    finally:
      self.structural_tokens = old_tokens


# ===== Rule Decorator =====


def rule(fn: Callable = None, *, name: Optional[str] = None, capture: bool = True):
  """Decorator for parser rules."""

  def decorator(func):
    def wrapper(self: Parser, *args, **kwargs):
      # Get rule name
      rule_name = name or func.__name__

      # Track tokens if capturing
      if capture:
        captured_tokens = []

        # Monkey-patch consume to track tokens
        original_consume = self.tokens.consume

        def tracking_consume():
          token = original_consume()
          captured_tokens.append(token)
          return token

        self.tokens.consume = tracking_consume

      try:
        # Execute rule
        result = func(self, *args, **kwargs)

        # Create node if capturing
        if capture and captured_tokens:
          node = Node(rule_name, captured_tokens)
          return node

        return result
      finally:
        # Restore original consume
        if capture:
          self.tokens.consume = original_consume

    return wrapper

  if fn is None:
    return decorator
  return decorator(fn)


# ===== Visitor Pattern =====


class Visitor:
  """Base class for tree traversal."""

  def visit(self, node: Union[Node, Token]) -> Any:
    """Visit a node or token."""
    if isinstance(node, Token):
      return self.visit_token(node)

    method_name = f"visit_{node.type}"
    method = getattr(self, method_name, self.generic_visit)
    return method(node)

  def visit_token(self, token: Token) -> Any:
    """Visit a token."""
    return token.value

  def generic_visit(self, node: Node) -> Any:
    """Default visitor for unhandled nodes."""
    for child in node.children:
      self.visit(child)
