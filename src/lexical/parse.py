"""
Recursive descent parsing framework with integrated observability.

Provides parser combinators and rule decorators for building parsers
that emit immutable syntax trees with built-in observation support.
"""

from typing import List, Optional, Callable, Any
from contextlib import contextmanager
from .tree import TreeBuilder, SyntaxTree, NodeView
from .observe import LexicalContext
from .tokenize import Token


class ParseError(Exception):
  """Raised when parsing fails."""

  pass


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


class Parser:
  """
  Base class for recursive descent parsers with integrated observability.

  Observability is automatic for all parsing operations including
  rule execution, token consumption, and backtracking.
  """

  def __init__(self, tokens: List[Token], obs_context: Optional[LexicalContext] = None):
    """
    Initialize parser with observability.

    Args:
        tokens: List of tokens to parse
        obs_context: Observability context or None for null context
    """
    # Initialize observability first
    self._obs = obs_context or LexicalContext.null()

    # Standard initialization
    self.tokens = TokenStream(tokens)
    self.builder = TreeBuilder(obs_context)  # Pass observability to builder
    self.structural_tokens = {"WHITESPACE", "COMMENT", "NEWLINE"}
    self.skip_structural = False
    self.control_tokens = {"EOF", "BOF"}

    # Emit parse start
    self._obs.emit_event("parse.start", token_count=len(tokens))

  # ===== Token Operations =====

  def consume(self) -> Token:
    """
    Consume next token with observation.

    Emits parse.consume event with token details.
    """
    if self.skip_structural:
      self._skip_structural_tokens()

    token = self.tokens.consume()

    # Only add content tokens to syntax tree
    if self._is_syntax_token(token):
      self.builder.add_token(token)

    # Emit consume event
    self._obs.emit_event("parse.consume", token_type=token.type, token_value=token.value)

    return token

  def expect(self, *types: str) -> Token:
    """
    Expect and consume token with observation.

    Emits parse.expect events for debugging.
    """
    if self.skip_structural:
      self._skip_structural_tokens()

    # Emit expectation event
    self._obs.emit_event("parse.expect.start", expected=types)

    token = self.tokens.expect(*types)
    if self._is_syntax_token(token):
      self.builder.add_token(token)

    # Emit success event
    self._obs.emit_event("parse.expect.success", expected=types, found=token.type)

    return token

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

  def _is_syntax_token(self, token: Token) -> bool:
    """Check if token should be part of syntax tree."""
    return token.type not in self.control_tokens and token.type not in self.structural_tokens

  # ===== Parser Entry Point =====

  def parse(self) -> SyntaxTree:
    """
    Parse tokens and build syntax tree with observation.

    Emits parse.start and parse.complete events, plus all
    intermediate parsing events.
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
      tree = SyntaxTree(frozen)
      self._obs.emit_event("parse.complete", node_count=len(tree.root))
      return tree

    except ParseError as e:
      position = self.tokens.peek().position if not self.tokens.at_end() else None
      self._obs.emit_error(str(e), position)
      raise
    except Exception as e:
      # Wrap other errors with parse context
      token = self.peek()
      if token:
        self._obs.emit_error(f"Parse failed: {str(e)}", token.position)
        raise ParseError(f"Parse failed at line {token.line}, column {token.column}: {str(e)}") from e
      else:
        self._obs.emit_error(f"Parse failed: {str(e)}", None)
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
    """
    Try alternatives in order with observation.

    Emits choice events and backtrack information.
    """
    last_error = None

    # Emit choice start
    self._obs.emit_event("parse.choice.start", alternatives=[alt.__name__ for alt in alternatives])

    for i, alt in enumerate(alternatives):
      pos = self.tokens.save()
      builder_depth = len(self.builder._stack)

      # Emit attempt event
      self._obs.emit_event("parse.choice.attempt", alternative=alt.__name__, index=i)

      try:
        result = alt()
        # Emit success
        self._obs.emit_event("parse.choice.success", alternative=alt.__name__, index=i)
        return result
      except ParseError as e:
        last_error = e
        self.tokens.restore(pos)
        # Restore builder state
        while len(self.builder._stack) > builder_depth:
          self.builder.abandon_node()

        # Emit backtrack
        self._obs.emit_backtrack(alt.__name__, str(e))

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


def rule(name: Optional[str] = None, capture: bool = True):
  """
  Decorator for parser rules with automatic observation.

  All rule execution is automatically observed with enter/exit
  events, timing, and parse stack tracking.

  Args:
      name: Custom rule name (defaults to function name)
      capture: Whether to create CST node
  """

  def decorator(func: Callable) -> Callable:
    rule_name = name or func.__name__

    def wrapper(self, *args, **kwargs):
      # Get position for context
      position = None
      if not self.tokens.at_end():
        token = self.tokens.peek()
        if token:
          position = token.position

      # Always observe rule execution
      with self._obs.rule(rule_name, position):
        if capture:
          with self.builder.node(rule_name):
            return func(self, *args, **kwargs)
        else:
          return func(self, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper

  return decorator


# ===== Visitor Pattern Support =====


class Visitor:
  """
  Base class for syntax tree visitors.

  Provides traversal and transformation capabilities
  for immutable syntax trees.
  """

  def visit(self, node: NodeView) -> Any:
    """
    Visit a node and its children.

    Calls visit_<kind> method if it exists,
    otherwise visits children.
    """
    method_name = f"visit_{node.kind}"
    method = getattr(self, method_name, None)

    if method:
      return method(node)
    else:
      # Default: visit children
      return self.generic_visit(node)

  def generic_visit(self, node: NodeView) -> Any:
    """Default visitor that processes children."""
    for child in node.children:
      self.visit(child)

  def transform(self, node: NodeView) -> NodeView:
    """
    Transform a node and its children.

    Returns a new transformed tree.
    """
    method_name = f"transform_{node.kind}"
    method = getattr(self, method_name, None)

    if method:
      return method(node)
    else:
      # Default: transform children
      return self.generic_transform(node)

  def generic_transform(self, node: NodeView) -> NodeView:
    """Default transformer that rebuilds with transformed children."""
    # Transform children
    new_children = []
    for child in node.children:
      transformed = self.transform(child)
      if transformed:
        new_children.append(transformed)

    # Rebuild node if children changed
    if new_children != list(node.children):
      return node.replace_children(new_children)
    return node
