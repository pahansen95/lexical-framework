"""
Recursive descent parsing framework with frozen tree construction.

Provides parser combinators and rule decorators for building parsers
that emit immutable syntax trees through an integrated builder pattern.
"""

from typing import List, Optional, Callable, Any
from contextlib import contextmanager
from tree import TreeBuilder, SyntaxTree, NodeView


class ParseError(Exception):
  """Raised when parsing fails"""

  pass


class TokenStream:
  """Manages navigation through tokens"""

  def __init__(self, tokens: List):
    self.tokens = tokens
    self.pos = 0

  def peek(self, offset: int = 0) -> Optional:
    """Look ahead without consuming"""
    idx = self.pos + offset
    return self.tokens[idx] if idx < len(self.tokens) else None

  def consume(self):
    """Consume and return current token"""
    if self.at_end():
      raise ParseError("Unexpected end of input")
    token = self.tokens[self.pos]
    self.pos += 1
    return token

  def match(self, *types: str) -> bool:
    """Check if current token matches types"""
    token = self.peek()
    return token and token.type in types

  def expect(self, *types: str):
    """Consume token of expected type"""
    token = self.peek()
    if not token:
      raise ParseError(f"Expected {types} but reached end")
    if token.type not in types:
      raise ParseError(f"Expected {types} but got {token.type} at line {token.line}")
    return self.consume()

  def at_end(self) -> bool:
    """Check if at end of stream"""
    return self.pos >= len(self.tokens)

  def save(self) -> int:
    """Save current position"""
    return self.pos

  def restore(self, pos: int):
    """Restore saved position"""
    self.pos = pos


class Parser:
  """Base class for recursive descent parsers"""

  def __init__(self, tokens: List):
    self.tokens = TokenStream(tokens)
    self.builder = TreeBuilder()
    self.structural_tokens = {"WHITESPACE", "COMMENT", "NEWLINE"}
    self.skip_structural = False
    # Control tokens that shouldn't appear in syntax tree
    self.control_tokens = {"EOF", "BOF"}

  # ===== Token Operations =====

  def consume(self):
    """Consume next token"""
    if self.skip_structural:
      self._skip_structural_tokens()

    token = self.tokens.consume()
    # Only add content tokens to syntax tree
    if self._is_syntax_token(token):
      self.builder.add_token(token)
    return token

  def expect(self, *types: str):
    """Expect and consume token"""
    if self.skip_structural:
      self._skip_structural_tokens()

    token = self.tokens.expect(*types)
    # Only add content tokens to syntax tree
    if self._is_syntax_token(token):
      self.builder.add_token(token)
    return token

  def match(self, *types: str) -> bool:
    """Check if next token matches"""
    if self.skip_structural:
      pos = self.tokens.save()
      self._skip_structural_tokens()
      result = self.tokens.match(*types)
      self.tokens.restore(pos)
      return result
    return self.tokens.match(*types)

  def peek(self) -> Optional:
    """Look at next token"""
    if self.skip_structural:
      pos = self.tokens.save()
      self._skip_structural_tokens()
      token = self.tokens.peek()
      self.tokens.restore(pos)
      return token
    return self.tokens.peek()

  def _skip_structural_tokens(self):
    """Skip over structural tokens"""
    while self.tokens.match(*self.structural_tokens):
      self.tokens.consume()

  def _is_syntax_token(self, token) -> bool:
    """Check if token should be part of syntax tree"""
    return token.type not in self.control_tokens

  # ===== Parser Entry Point =====

  def parse(self) -> SyntaxTree:
    """
    Parse tokens into syntax tree.

    Subclasses should override parse_root() to define grammar.
    This method handles EOF verification and tree building.
    """
    try:
      # Parse using grammar root
      self.parse_root()

      # Verify complete consumption
      if not self.match("EOF"):
        unexpected = self.peek()
        if unexpected:
          raise ParseError(
            f"Unexpected {unexpected.type} '{unexpected.value}' at line {unexpected.line}, column {unexpected.column}"
          )
        else:
          raise ParseError("Unexpected content at end of input")

      # Build and return tree
      frozen = self.builder.build()
      return SyntaxTree(frozen)

    except ParseError:
      # Re-raise parse errors with original context
      raise
    except Exception as e:
      # Wrap other errors with parse context
      token = self.peek()
      if token:
        raise ParseError(f"Parse failed at line {token.line}, column {token.column}: {str(e)}") from e
      else:
        raise ParseError(f"Parse failed: {str(e)}") from e

  def parse_root(self):
    """
    Parse grammar root. Override in subclasses.

    Example:
        def parse_root(self):
            self.expression()
    """
    raise NotImplementedError("Subclasses must implement parse_root()")

  # ===== Parser Combinators =====

  def choice(self, *alternatives: Callable) -> Any:
    """Try alternatives in order"""
    last_error = None

    for alt in alternatives:
      pos = self.tokens.save()
      builder_depth = len(self.builder._stack)

      try:
        return alt()
      except ParseError as e:
        last_error = e
        self.tokens.restore(pos)
        # Restore builder state
        while len(self.builder._stack) > builder_depth:
          self.builder.abandon_node()

    raise last_error or ParseError("No alternatives matched")

  def many(self, parser_fn: Callable) -> List[Any]:
    """Parse zero or more occurrences"""
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
    """Parse one or more occurrences"""
    results = [parser_fn()]
    results.extend(self.many(parser_fn))
    return results

  def optional(self, parser_fn: Callable) -> Optional[Any]:
    """Parse zero or one occurrence"""
    pos = self.tokens.save()
    try:
      return parser_fn()
    except ParseError:
      self.tokens.restore(pos)
      return None

  def separated(self, parser_fn: Callable, delimiter: str) -> List[Any]:
    """Parse delimited sequence"""
    results = [parser_fn()]
    while self.match(delimiter):
      self.consume()
      results.append(parser_fn())
    return results

  # ===== Context Managers =====

  @contextmanager
  def structural_handling(self, enabled: bool):
    """Temporarily change structural token handling"""
    old_value = self.skip_structural
    self.skip_structural = enabled
    try:
      yield
    finally:
      self.skip_structural = old_value

  @contextmanager
  def custom_structural(self, tokens: set):
    """Temporarily use custom structural tokens"""
    old_tokens = self.structural_tokens
    self.structural_tokens = tokens
    try:
      yield
    finally:
      self.structural_tokens = old_tokens


def rule(fn: Callable = None, *, name: Optional[str] = None, capture: bool = True):
  """Decorator for parser rules"""

  def decorator(func):
    def wrapper(self: Parser, *args, **kwargs):
      rule_name = name or func.__name__

      if capture:
        self.builder.start_node(rule_name)

      try:
        result = func(self, *args, **kwargs)

        if capture:
          self.builder.finish_node(rule_name)

        return result
      except Exception:
        if capture:
          self.builder.abandon_node()
        raise

    wrapper.__name__ = func.__name__
    return wrapper

  return decorator if fn is None else decorator(fn)


class Visitor:
  """Base class for tree traversal"""

  def visit(self, node: NodeView) -> Any:
    """Visit a node or token"""
    method_name = f"visit_{node.kind}"
    method = getattr(self, method_name, self.generic_visit)
    return method(node)

  def generic_visit(self, node: NodeView) -> Any:
    """Default visitor for unhandled nodes"""
    for child in node.children:
      self.visit(child)
