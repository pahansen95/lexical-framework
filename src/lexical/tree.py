"""
Immutable syntax tree construction and navigation.

Provides frozen tree data structures and builder patterns for creating
immutable syntax trees with efficient structural sharing.
"""

import weakref
from dataclasses import dataclass
from typing import Any, List, Optional, Union, Iterator, Tuple, Dict
from .tokenize import Token
from .observe import LexicalContext, Position as ObsPosition


# ===== Frozen Data Structures =====


@dataclass(frozen=True)
class FrozenToken:
  """Immutable token in syntax tree."""

  __slots__ = ("type", "value", "pos", "line", "column")

  type: str
  value: str
  pos: int
  line: int
  column: int

  @classmethod
  def from_lex_token(cls, token: Token) -> "FrozenToken":
    """Create from lexer token."""
    return cls(type=token.type, value=token.value, pos=token.pos, line=token.line, column=token.column)


@dataclass(frozen=True)
class FrozenNode:
  """Immutable internal node in syntax tree."""

  __slots__ = ("kind", "children")

  kind: str
  children: tuple[Union["FrozenNode", FrozenToken], ...]

  def __len__(self) -> int:
    """Total node count including self."""
    return 1 + sum(len(c) if isinstance(c, FrozenNode) else 1 for c in self.children)


# Union type for tree elements
FrozenElement = Union[FrozenNode, FrozenToken]


# ===== View Layer =====


class NodeView:
  """
  Lazy view over frozen tree nodes.

  Provides navigation and query methods without modifying
  the underlying frozen structure.
  """

  __slots__ = ("_frozen", "_parent_ref", "_index", "_child_views")

  def __init__(self, frozen: FrozenElement, parent: Optional["NodeView"] = None, index: int = 0):
    self._frozen = frozen
    self._parent_ref = weakref.ref(parent) if parent else None
    self._index = index
    self._child_views: Optional[List["NodeView"]] = None

  @property
  def kind(self) -> str:
    """Node type or token type."""
    if isinstance(self._frozen, FrozenNode):
      return self._frozen.kind
    else:
      return self._frozen.type

  @property
  def is_token(self) -> bool:
    """Check if this is a token."""
    return isinstance(self._frozen, FrozenToken)

  @property
  def text(self) -> Optional[str]:
    """Token text if applicable."""
    if isinstance(self._frozen, FrozenToken):
      return self._frozen.value
    return None

  @property
  def position(self) -> Optional[ObsPosition]:
    """Source position if token."""
    if isinstance(self._frozen, FrozenToken):
      return ObsPosition(line=self._frozen.line, column=self._frozen.column, offset=self._frozen.pos)
    return None

  @property
  def parent(self) -> Optional["NodeView"]:
    """Parent node if any."""
    return self._parent_ref() if self._parent_ref else None

  @property
  def children(self) -> List["NodeView"]:
    """Child nodes (cached)."""
    if self._child_views is None:
      if isinstance(self._frozen, FrozenNode):
        self._child_views = [NodeView(child, self, i) for i, child in enumerate(self._frozen.children)]
      else:
        self._child_views = []
    return self._child_views

  def find_at_position(self, position: int) -> Optional["NodeView"]:
    """Find deepest node containing position."""
    if self.is_token:
      token = self._frozen
      if token.pos <= position < token.pos + len(token.value):
        return self
      return None

    # Check children
    for child in self.children:
      if result := child.find_at_position(position):
        return result
    return None

  def find_all(self, kind: str) -> List["NodeView"]:
    """Find all nodes of given kind."""
    results = []

    def search(node: NodeView):
      if node.kind == kind:
        results.append(node)
      for child in node.children:
        search(child)

    search(self)
    return results

  def walk(self) -> Iterator["NodeView"]:
    """Walk all nodes depth-first."""
    yield self
    for child in self.children:
      yield from child.walk()

  def path_to_root(self) -> List["NodeView"]:
    """Get path from this node to root."""
    path = []
    node = self
    while node:
      path.append(node)
      node = node.parent
    return list(reversed(path))

  def replace_children(self, new_children: List[FrozenElement]) -> FrozenNode:
    """Create new node with replaced children."""
    if self.is_token:
      raise ValueError("Cannot replace children of token")
    return FrozenNode(self.kind, tuple(new_children))


# ===== Builder Pattern =====


@dataclass
class TreeBuilder:
  """
  Builds immutable syntax trees with structural sharing.

  Optionally integrates with observability for AST node events.
  """

  def __init__(self, obs_context: Optional[LexicalContext] = None):
    """
    Initialize builder with optional observability.

    Args:
        obs_context: Optional observability context for AST events
    """
    self._obs = obs_context or LexicalContext.null()
    self._stack: List[List[FrozenElement]] = [[]]
    self._node_cache: Dict[Tuple, FrozenNode] = {}
    self._token_cache: Dict[Tuple, FrozenToken] = {}
    self._cache_limit = 100

  def start_node(self, kind: str) -> "TreeBuilder":
    """Begin building a new node."""
    self._stack.append([])
    return self

  def add_token(self, token: Token) -> "TreeBuilder":
    """Add token with caching."""
    # Create cache key
    key = (token.type, token.value, token.pos, token.line, token.column)

    if key not in self._token_cache:
      frozen = FrozenToken.from_lex_token(token)
      self._token_cache[key] = frozen

      # Emit AST token event if observing
      if self._obs.has_handlers():
        self._obs.emit_ast_node("token", {"type": token.type, "value": token.value}, token.position)

    self._stack[-1].append(self._token_cache[key])
    return self

  def add_frozen(self, element: FrozenElement) -> "TreeBuilder":
    """Add pre-built element."""
    self._stack[-1].append(element)
    return self

  def finish_node(self, kind: str) -> "TreeBuilder":
    """Complete current node with caching."""
    if len(self._stack) <= 1:
      raise ValueError("No node to finish")

    children = tuple(self._stack.pop())

    # Cache small nodes
    if len(children) <= self._cache_limit:
      cache_key = (kind, tuple(id(c) for c in children))
      if cache_key in self._node_cache:
        node = self._node_cache[cache_key]
      else:
        node = FrozenNode(kind, children)
        self._node_cache[cache_key] = node
    else:
      node = FrozenNode(kind, children)

    # Emit AST node event if observing
    if self._obs.has_handlers():
      self._obs.emit_ast_node(
        kind,
        {"child_count": len(children)},
        None,  # Internal nodes don't have position
      )

    self._stack[-1].append(node)
    return self

  def abandon_node(self) -> "TreeBuilder":
    """Cancel current node."""
    if len(self._stack) > 1:
      self._stack.pop()
    return self

  def build(self) -> FrozenNode:
    """Get final tree."""
    if len(self._stack) != 1:
      raise ValueError(f"Unclosed nodes: {len(self._stack) - 1}")
    if len(self._stack[0]) != 1:
      raise ValueError("Expected single root")

    root = self._stack[0][0]
    if not isinstance(root, FrozenNode):
      raise TypeError("Root must be FrozenNode")
    return root

  # Context manager support
  def node(self, kind: str):
    """Context manager for node building."""

    class NodeContext:
      def __init__(self, builder: TreeBuilder, kind: str):
        self.builder = builder
        self.kind = kind

      def __enter__(self):
        self.builder.start_node(self.kind)
        return self.builder

      def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
          self.builder.finish_node(self.kind)
        else:
          self.builder.abandon_node()
        return False

    return NodeContext(self, kind)


# ===== High-Level API =====


class SyntaxTree:
  """User-facing tree interface with thread-safe view caching."""

  def __init__(self, frozen_root: FrozenNode):
    if not isinstance(frozen_root, FrozenNode):
      raise TypeError("Root must be FrozenNode")
    self._frozen_root = frozen_root
    self._root_view = None

  @property
  def root(self) -> NodeView:
    """Get root view (cached)."""
    if self._root_view is None:
      self._root_view = NodeView(self._frozen_root)
    return self._root_view

  def find_at_position(self, position: int) -> Optional[NodeView]:
    """Find node at character position."""
    return self.root.find_at_position(position)

  def find_all(self, kind: str) -> List[NodeView]:
    """Find all nodes of given kind."""
    return self.root.find_all(kind)

  def walk(self) -> Iterator[NodeView]:
    """Walk all nodes depth-first."""
    return self.root.walk()

  def dump(self, indent: int = 0) -> str:
    """Debug representation."""

    def dump_node(node: NodeView, level: int) -> str:
      prefix = "  " * level
      if node.is_token:
        return f"{prefix}{node.kind}: {repr(node.text)}"
      else:
        lines = [f"{prefix}{node.kind}:"]
        for child in node.children:
          lines.append(dump_node(child, level + 1))
        return "\n".join(lines)

    return dump_node(self.root, indent)

  def __len__(self) -> int:
    """Total node count."""
    return len(self._frozen_root)


# ===== Visitor Pattern =====


class TreeVisitor:
  """Base visitor for tree traversal."""

  def visit(self, node: NodeView) -> Any:
    """Dispatch to specific visitor method."""
    method_name = f"visit_{node.kind}"
    method = getattr(self, method_name, self.generic_visit)
    return method(node)

  def generic_visit(self, node: NodeView) -> Any:
    """Default: visit all children."""
    for child in node.children:
      self.visit(child)


class TreeTransformer(TreeVisitor):
  """Base transformer creating new trees."""

  def __init__(self):
    self.builder = TreeBuilder()

  def transform(self, tree: SyntaxTree) -> SyntaxTree:
    """Transform entire tree."""
    frozen = self._transform_node(tree.root)
    return SyntaxTree(frozen)

  def _transform_node(self, node: NodeView) -> FrozenElement:
    """Transform single node."""
    if node.is_token:
      return node._frozen

    # Build new node with transformed children
    children = []
    for child in node.children:
      transformed = self._transform_node(child)
      if transformed:
        children.append(transformed)

    return FrozenNode(node.kind, tuple(children))
