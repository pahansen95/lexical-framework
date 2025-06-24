"""
Recursive descent parsing framework with integrated tree building.

Provides unified parsing and tree construction through a single coherent
system, eliminating coordination complexity between separate components.
"""

from typing import List, Optional, Callable, TypeVar, NamedTuple, Dict, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

from .tree import SyntaxTree, FrozenNode, FrozenToken, FrozenElement
from .observe import LexicalContext
from .tokenize import Token
from .position import Position


# Type variables for generic parser combinators
T = TypeVar("T")


class ParseError(Exception):
  """Raised when parsing fails."""

  pass


class BuildFrame(NamedTuple):
  """Frame tracking node construction state."""

  kind: str
  start_depth: int


@dataclass
class ParseState:
  """Complete parser state for save/restore."""

  token_pos: int
  build_depth: int
  node_depth: int


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
    return token is not None and token.type in types

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

  def restore(self, pos: int) -> None:
    """Restore saved position."""
    self.pos = pos


class Parser:
  """
  Parser with consolidated tree building responsibility.

  Combines parsing and tree construction into a single cohesive flow,
  eliminating coordination complexity between separate components.
  """

  def __init__(self, tokens: List[Token], obs_context: Optional[LexicalContext] = None):
    """
    Initialize parser with unified building state.

    Args:
        tokens: List of tokens to parse
        obs_context: Observability context or None for null context
    """
    # Boundary validation
    assert isinstance(tokens, list), f"tokens must be list, got {type(tokens).__name__}"
    assert tokens, "tokens list cannot be empty"
    assert all(isinstance(t, Token) for t in tokens), "all elements must be Token instances"
    assert tokens[-1].type == "EOF", "tokens must end with EOF token"

    # Check for duplicate EOF
    eof_count = sum(1 for t in tokens if t.type == "EOF")
    assert eof_count == 1, f"Expected exactly one EOF token, found {eof_count}"

    # Core state
    self.tokens = TokenStream(tokens)
    self._obs = obs_context or LexicalContext.null()

    # Unified building state - no separate TreeBuilder
    self._build_stack: List[BuildFrame] = []
    self._node_stack: List[List[FrozenElement]] = [[]]  # Stack of children lists
    self._node_cache: Dict[Tuple, FrozenNode] = {}
    self._token_cache: Dict[Tuple[str, str, Position], FrozenToken] = {}
    self._cache_limit = 100

    # Token handling
    self.structural_tokens = {"WHITESPACE", "COMMENT", "NEWLINE"}
    self.skip_structural = False
    self.control_tokens = {"EOF", "BOF"}

    # Emit parse start
    self._obs.emit_event("parse.start", token_count=len(tokens))

  # ===== Building Primitives =====

  def _start_node(self, kind: str) -> None:
    """Begin building a node."""
    self._build_stack.append(BuildFrame(kind, len(self._node_stack)))
    self._node_stack.append([])

  def _finish_node(self) -> None:
    """Complete node and add to parent."""
    frame = self._build_stack.pop()
    children = tuple(self._node_stack.pop())

    # Create frozen node with caching
    node = self._create_frozen_node(frame.kind, children)
    self._node_stack[-1].append(node)

  def _abandon_node(self) -> None:
    """Cancel node construction."""
    self._build_stack.pop()
    self._node_stack.pop()

  def _add_element(self, element: FrozenElement) -> None:
    """Add element to current node being built."""
    if self._node_stack:
      self._node_stack[-1].append(element)

  def _create_frozen_node(self, kind: str, children: Tuple[FrozenElement, ...]) -> FrozenNode:
    """Create frozen node with caching for small nodes."""
    # Cache small nodes for memory efficiency
    if len(children) <= self._cache_limit:
      cache_key = (kind, tuple(id(c) for c in children))
      if cache_key in self._node_cache:
        return self._node_cache[cache_key]

      node = FrozenNode(kind, children)
      self._node_cache[cache_key] = node
      return node

    return FrozenNode(kind, children)

  def _create_frozen_token(self, token: Token) -> FrozenToken:
    """Create frozen token with caching."""
    cache_key = (token.type, token.value, token.position)

    if cache_key not in self._token_cache:
      frozen = FrozenToken.from_lex_token(token)
      self._token_cache[cache_key] = frozen

      # Emit AST token event if observing
      if self._obs.has_handlers():
        self._obs.emit_ast_node("token", {"type": token.type, "value": token.value}, token.position)

    return self._token_cache[cache_key]

  # ===== Unified Rule Context =====

  @contextmanager
  def rule(self, name: str, *, build: bool = True):
    """
    Combined rule execution and tree building context.

    Args:
        name: Rule/node name
        build: Whether to create a syntax node
    """
    # Get position for observation
    position: Optional[Position] = None
    if not self.tokens.at_end():
      if token := self.tokens.peek():
        position = token.position

    # Start observation
    with self._obs.rule(name, position):
      if build:
        # Start building
        self._start_node(name)
        try:
          yield self  # Allow access to parser in context
          self._finish_node()
        except Exception:
          self._abandon_node()
          raise
      else:
        # Just observe, no building
        yield self

  def with_node(self, kind: str):
    """Create node with custom kind."""
    return self.rule(kind, build=True)

  def without_node(self):
    """Execute without building."""
    return self.rule("anonymous", build=False)

  # ===== Token Operations =====

  def consume(self) -> Token:
    """Consume token and add to current node if building."""
    if self.skip_structural:
      self._skip_structural_tokens()

    token = self.tokens.consume()

    # Add syntax tokens to current node
    if self._is_syntax_token(token) and self._node_stack:
      frozen = self._create_frozen_token(token)
      self._add_element(frozen)

    # Emit consume event
    self._obs.emit_event("parse.consume", token_type=token.type, token_value=token.value)

    return token

  def expect(self, *types: str) -> Token:
    """Expect token types and add to tree."""
    if self.skip_structural:
      self._skip_structural_tokens()

    # Emit expectation event
    self._obs.emit_event("parse.expect.start", expected=types)

    token = self.tokens.expect(*types)

    if self._is_syntax_token(token) and self._node_stack:
      frozen = self._create_frozen_token(token)
      self._add_element(frozen)

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

  def _skip_structural_tokens(self) -> None:
    """Skip over structural tokens."""
    while self.tokens.match(*self.structural_tokens):
      self.tokens.consume()

  def _is_syntax_token(self, token: Token) -> bool:
    """Check if token should be part of syntax tree."""
    return token.type not in self.control_tokens and token.type not in self.structural_tokens

  # ===== State Management =====

  def _save_state(self) -> ParseState:
    """Save complete parser state."""
    return ParseState(
      token_pos=self.tokens.save(), build_depth=len(self._build_stack), node_depth=len(self._node_stack)
    )

  def _restore_state(self, state: ParseState) -> None:
    """Restore complete parser state atomically."""
    self.tokens.restore(state.token_pos)

    # Restore building state
    while len(self._build_stack) > state.build_depth:
      self._build_stack.pop()
    while len(self._node_stack) > state.node_depth:
      self._node_stack.pop()

  # ===== Parser Entry Point =====

  def parse(self) -> SyntaxTree:
    """Parse tokens into syntax tree."""
    with self.rule("parse", build=False):  # Don't build a parse node
      try:
        # Parse using grammar root
        self.parse_root()

        # Verify complete
        if not self.match("EOF"):
          unexpected = self.peek()
          if unexpected:
            raise ParseError(
              f"Unexpected {unexpected.type} '{unexpected.value}' at line {unexpected.line}, column {unexpected.column}"
            )
          else:
            raise ParseError("Unexpected content at end of input")

        # Extract root from building state
        if len(self._node_stack) != 1:
          raise ParseError(f"Incomplete parsing: {len(self._node_stack)} levels")
        if len(self._node_stack[0]) != 1:
          raise ParseError(f"Multiple roots: {len(self._node_stack[0])}")

        root = self._node_stack[0][0]
        if not isinstance(root, FrozenNode):
          raise TypeError("Root must be FrozenNode")

        tree = SyntaxTree(root)
        self._obs.emit_event("parse.complete", node_count=len(tree))
        return tree

      except ParseError as e:
        position = self.tokens.peek().position if not self.tokens.at_end() else None
        self._obs.emit_error(str(e), position)
        raise
      except Exception as e:
        token = self.peek()
        if token:
          self._obs.emit_error(f"Parse failed: {str(e)}", token.position)
          raise ParseError(f"Parse failed at line {token.line}, column {token.column}: {str(e)}") from e
        else:
          self._obs.emit_error(f"Parse failed: {str(e)}", None)
          raise ParseError(f"Parse failed: {str(e)}") from e

  def parse_root(self) -> None:
    """
    Parse grammar root. Override in subclasses.

    Example:
        def parse_root(self):
            self.expression()
    """
    raise NotImplementedError("Subclasses must implement parse_root()")

  # ===== Parser Combinators =====

  def choice(self, *alternatives: Callable[[], T]) -> T:
    """Try alternatives with automatic tree rollback."""
    last_error: Optional[ParseError] = None

    # Emit choice start
    self._obs.emit_event("parse.choice.start", alternatives=[alt.__name__ for alt in alternatives])

    for i, alt in enumerate(alternatives):
      # Save complete state
      state = self._save_state()

      # Emit attempt event
      self._obs.emit_event("parse.choice.attempt", alternative=alt.__name__, index=i)

      try:
        result = alt()
        # Emit success
        self._obs.emit_event("parse.choice.success", alternative=alt.__name__, index=i)
        return result
      except ParseError as e:
        last_error = e
        # Restore complete state atomically
        self._restore_state(state)
        # Emit backtrack
        self._obs.emit_backtrack(alt.__name__, str(e))

    raise last_error or ParseError("No alternatives matched")

  def many(self, parser_fn: Callable[[], T]) -> List[T]:
    """Parse zero or more occurrences."""
    results: List[T] = []
    while True:
      state = self._save_state()
      try:
        results.append(parser_fn())
      except ParseError:
        self._restore_state(state)
        break
    return results

  def some(self, parser_fn: Callable[[], T]) -> List[T]:
    """Parse one or more occurrences."""
    results = [parser_fn()]
    results.extend(self.many(parser_fn))
    return results

  def optional(self, parser_fn: Callable[[], T]) -> Optional[T]:
    """Parse zero or one occurrence."""
    state = self._save_state()
    try:
      return parser_fn()
    except ParseError:
      self._restore_state(state)
      return None

  def separated(self, parser_fn: Callable[[], T], delimiter: str) -> List[T]:
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


def rule(name: Optional[str] = None, *, build: bool = True):
  """
  Simplified rule decorator using Parser's unified context.

  Args:
      name: Custom rule name (defaults to function name)
      build: Whether to create CST node
  """

  def decorator(func: Callable) -> Callable:
    rule_name = name or func.__name__

    def wrapper(self: Parser, *args, **kwargs):
      with self.rule(rule_name, build=build):
        return func(self, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper

  return decorator
