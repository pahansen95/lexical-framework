"""
Immutable syntax tree data structures and navigation.

Provides frozen tree representations and view layer for navigating
immutable syntax trees with efficient structural sharing.
"""

import weakref
from dataclasses import dataclass
from typing import List, Optional, Union, Iterator, Set, TypeVar, Generic
from .tokenize import Token
from .position import Position


# Type variable for generic visitors
T = TypeVar("T")


# ===== Frozen Data Structures =====


@dataclass(frozen=True)
class FrozenToken:
  """Immutable token in syntax tree with unified position."""

  __slots__ = ("type", "value", "position")

  type: str
  value: str
  position: Position

  @classmethod
  def from_lex_token(cls, token: Token) -> "FrozenToken":
    """Create from lexer token - direct position copy."""
    return cls(type=token.type, value=token.value, position=token.position)


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

  __slots__ = ("_frozen", "_parent_ref", "_index", "_child_views", "__weakref__")

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
  def position(self) -> Optional[Position]:
    """Source position if token - now returns unified Position."""
    if isinstance(self._frozen, FrozenToken):
      return self._frozen.position
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

  @property
  def line(self) -> Optional[int]:
    """Line number if token."""
    pos = self.position
    return pos.line if pos else None

  @property
  def column(self) -> Optional[int]:
    """Column number if token."""
    pos = self.position
    return pos.column if pos else None

  def find_at_position(self, offset: int) -> Optional["NodeView"]:
    """Find deepest node containing offset."""
    if self.is_token:
      pos = self.position
      if pos and pos.offset <= offset < pos.offset + len(self._frozen.value):
        return self
      return None

    # Check children
    for child in self.children:
      if result := child.find_at_position(offset):
        return result
    return None

  def find_all(self, kind: str) -> List["NodeView"]:
    """Find all nodes of given kind."""
    results: List["NodeView"] = []

    def search(node: NodeView) -> None:
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
    path: List["NodeView"] = []
    node: Optional["NodeView"] = self
    while node:
      path.append(node)
      node = node.parent
    return list(reversed(path))

  def replace_children(self, new_children: List[FrozenElement]) -> FrozenNode:
    """Create new node with replaced children."""
    if self.is_token:
      raise ValueError("Cannot replace children of token")
    return FrozenNode(self.kind, tuple(new_children))


# ===== High-Level API =====


class SyntaxTree:
  """User-facing tree interface with thread-safe view caching."""

  def __init__(self, frozen_root: FrozenNode):
    # Boundary validation
    assert isinstance(frozen_root, FrozenNode), f"Root must be FrozenNode, got {type(frozen_root).__name__}"
    assert frozen_root.kind, "Root node must have a kind"
    assert self._validate_no_cycles(frozen_root), "Tree contains cycles"

    self._frozen_root = frozen_root
    self._root_view: Optional[NodeView] = None

  @property
  def root(self) -> NodeView:
    """Get root view (cached)."""
    if self._root_view is None:
      self._root_view = NodeView(self._frozen_root)
    return self._root_view

  def find_at_position(self, offset: int) -> Optional[NodeView]:
    """Find node at character offset."""
    return self.root.find_at_position(offset)

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

  @staticmethod
  def _validate_no_cycles(node: FrozenNode, seen: Optional[Set[int]] = None) -> bool:
    """Ensure tree has no circular references."""
    if seen is None:
      seen = set()

    node_id = id(node)
    if node_id in seen:
      return False
    seen.add(node_id)

    if isinstance(node, FrozenNode):
      for child in node.children:
        if isinstance(child, FrozenNode):
          if not SyntaxTree._validate_no_cycles(child, seen):
            return False
    return True


# ===== Visitor Pattern =====


class TreeVisitor(Generic[T]):
  """Base visitor for tree traversal."""

  def visit(self, node: NodeView) -> T:
    """Dispatch to specific visitor method."""
    method_name = f"visit_{node.kind}"
    method = getattr(self, method_name, self.generic_visit)
    return method(node)

  def generic_visit(self, node: NodeView) -> T:
    """Default: visit all children."""
    raise NotImplementedError("Must implement generic_visit with return type T")


class TreeTransformer(TreeVisitor[FrozenElement]):
  """Base transformer creating new trees."""

  def transform(self, tree: SyntaxTree) -> SyntaxTree:
    """Transform entire tree."""
    frozen = self._transform_node(tree.root)
    if not isinstance(frozen, FrozenNode):
      raise TypeError("Root transformation must return FrozenNode")
    return SyntaxTree(frozen)

  def _transform_node(self, node: NodeView) -> FrozenElement:
    """Transform single node."""
    if node.is_token:
      return node._frozen

    # Build new node with transformed children
    children: List[FrozenElement] = []
    for child in node.children:
      transformed = self._transform_node(child)
      if transformed:
        children.append(transformed)

    return FrozenNode(node.kind, tuple(children))

  def generic_visit(self, node: NodeView) -> FrozenElement:
    """Default implementation delegates to _transform_node."""
    return self._transform_node(node)
