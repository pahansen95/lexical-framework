"""
Immutable syntax tree infrastructure with structural sharing.

Implements frozen nodes for persistence, view facades for navigation,
and builder patterns for incremental construction of thread-safe trees.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Union, Any, Iterator
import weakref


# ===== Frozen Layer (Immutable Structure) =====


@dataclass(frozen=True, slots=True)
class FrozenToken:
  """Immutable token representation"""

  kind: str
  text: str
  width: int
  line: int
  column: int

  @classmethod
  def from_lex_token(cls, token) -> "FrozenToken":
    """Create from lexer token"""
    return cls(kind=token.type, text=token.value, width=len(token.value), line=token.line, column=token.column)


class FrozenNode:
  """Immutable node with structural sharing"""

  __slots__ = ("kind", "children", "_width", "_hash")

  def __init__(self, kind: str, children: Tuple[Union["FrozenNode", FrozenToken], ...]):
    self.kind = kind
    self.children = children
    self._width = None
    self._hash = None

  @property
  def width(self) -> int:
    if self._width is None:
      self._width = sum(c.width for c in self.children)
    return self._width

  def __hash__(self) -> int:
    if self._hash is None:
      self._hash = hash((self.kind, self.children))
    return self._hash

  def __eq__(self, other) -> bool:
    return isinstance(other, FrozenNode) and self.kind == other.kind and self.children == other.children


# ===== View Layer (Navigation Facade) =====


class NodeView:
  """Navigation facade over frozen nodes"""

  __slots__ = ("_frozen", "_parent_ref", "_position", "_cached_children", "_index", "__weakref__")

  def __init__(
    self, frozen: Union[FrozenNode, FrozenToken], parent: Optional["NodeView"] = None, position: int = 0, index: int = 0
  ):
    self._frozen = frozen
    self._parent_ref = weakref.ref(parent) if parent else None
    self._position = position
    self._index = index
    self._cached_children = None

  @property
  def kind(self) -> str:
    return self._frozen.kind

  @property
  def parent(self) -> Optional["NodeView"]:
    return self._parent_ref() if self._parent_ref else None

  @property
  def position(self) -> int:
    return self._position

  @property
  def width(self) -> int:
    return self._frozen.width

  @property
  def end_position(self) -> int:
    return self._position + self.width

  @property
  def is_token(self) -> bool:
    return isinstance(self._frozen, FrozenToken)

  @property
  def text(self) -> Optional[str]:
    return self._frozen.text if self.is_token else None

  @property
  def line(self) -> Optional[int]:
    return self._frozen.line if self.is_token else None

  @property
  def column(self) -> Optional[int]:
    return self._frozen.column if self.is_token else None

  @property
  def children(self) -> List["NodeView"]:
    if self._cached_children is None and not self.is_token:
      self._cached_children = []
      pos = self._position
      for i, child in enumerate(self._frozen.children):
        view = NodeView(child, self, pos, i)
        self._cached_children.append(view)
        pos += child.width
    return self._cached_children or []

  def child(self, index: int) -> Optional["NodeView"]:
    """Get child at index"""
    children = self.children
    return children[index] if 0 <= index < len(children) else None

  def find_at_position(self, pos: int) -> Optional["NodeView"]:
    """Find deepest node containing position"""
    if not (self.position <= pos < self.end_position):
      return None

    for child in self.children:
      if result := child.find_at_position(pos):
        return result

    return self


# ===== Builder Pattern =====


class TreeBuilder:
  """Constructs frozen trees incrementally"""

  def __init__(self):
    self._stack = [[]]
    self._token_cache = {}
    self._node_cache = {}
    self._cache_limit = 3

  def start_node(self, kind: str) -> "TreeBuilder":
    """Begin new node"""
    self._stack.append([])
    return self

  def add_token(self, token) -> "TreeBuilder":
    """Add token with interning"""
    key = (token.type, token.value)
    if key not in self._token_cache:
      self._token_cache[key] = FrozenToken.from_lex_token(token)

    self._stack[-1].append(self._token_cache[key])
    return self

  def add_frozen(self, element: Union[FrozenNode, FrozenToken]) -> "TreeBuilder":
    """Add pre-built element"""
    self._stack[-1].append(element)
    return self

  def finish_node(self, kind: str) -> "TreeBuilder":
    """Complete current node with caching"""
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

    self._stack[-1].append(node)
    return self

  def abandon_node(self) -> "TreeBuilder":
    """Cancel current node"""
    if len(self._stack) > 1:
      self._stack.pop()
    return self

  def build(self) -> FrozenNode:
    """Get final tree"""
    if len(self._stack) != 1:
      raise ValueError(f"Unclosed nodes: {len(self._stack) - 1}")
    if len(self._stack[0]) != 1:
      raise ValueError("Expected single root")

    root = self._stack[0][0]
    if not isinstance(root, FrozenNode):
      raise TypeError("Root must be FrozenNode")
    return root


# ===== High-Level API =====


class SyntaxTree:
  """User-facing tree interface"""

  def __init__(self, frozen_root: FrozenNode):
    self._frozen_root = frozen_root
    self._root_view = None

  @property
  def root(self) -> NodeView:
    """Get root view"""
    if self._root_view is None:
      self._root_view = NodeView(self._frozen_root)
    return self._root_view

  def find_at_position(self, position: int) -> Optional[NodeView]:
    """Find node at character position"""
    return self.root.find_at_position(position)

  def find_all(self, kind: str) -> List[NodeView]:
    """Find all nodes of given kind"""
    results = []

    def search(node: NodeView):
      if node.kind == kind:
        results.append(node)
      for child in node.children:
        search(child)

    search(self.root)
    return results

  def walk(self) -> Iterator[NodeView]:
    """Walk all nodes depth-first"""

    def traverse(node: NodeView):
      yield node
      for child in node.children:
        yield from traverse(child)

    return traverse(self.root)

  def dump(self, indent: int = 0) -> str:
    """Debug representation"""

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


# ===== Visitor Pattern =====


class TreeVisitor:
  """Base visitor for tree traversal"""

  def visit(self, node: NodeView) -> Any:
    """Dispatch to specific visitor method"""
    method_name = f"visit_{node.kind}"
    method = getattr(self, method_name, self.generic_visit)
    return method(node)

  def generic_visit(self, node: NodeView) -> Any:
    """Default: visit all children"""
    for child in node.children:
      self.visit(child)


class TreeTransformer(TreeVisitor):
  """Base transformer creating new trees"""

  def __init__(self):
    self.builder = TreeBuilder()

  def transform(self, tree: SyntaxTree) -> SyntaxTree:
    """Transform entire tree"""
    frozen = self._transform_node(tree.root)
    return SyntaxTree(frozen)

  def _transform_node(self, node: NodeView) -> Union[FrozenNode, FrozenToken]:
    """Transform single node"""
    if node.is_token:
      return node._frozen

    # Build new node with transformed children
    children = []
    for child in node.children:
      transformed = self._transform_node(child)
      if transformed:  # Allow filtering
        children.append(transformed)

    return FrozenNode(node.kind, tuple(children))


# ===== Tree Utilities =====


def tree_diff(tree1: SyntaxTree, tree2: SyntaxTree) -> List[Tuple[str, NodeView, Optional[NodeView]]]:
  """Find differences between two trees"""
  differences = []

  def compare_nodes(node1: NodeView, node2: Optional[NodeView], path: str = ""):
    if node2 is None:
      differences.append(("removed", node1, None))
      return

    if node1.kind != node2.kind:
      differences.append(("changed", node1, node2))
      return

    if node1.is_token:
      if node1.text != node2.text:
        differences.append(("changed", node1, node2))
    else:
      # Compare children
      children1 = node1.children
      children2 = node2.children

      for i, child1 in enumerate(children1):
        if i < len(children2):
          compare_nodes(child1, children2[i], f"{path}/{i}")
        else:
          differences.append(("removed", child1, None))

      for i in range(len(children1), len(children2)):
        differences.append(("added", None, children2[i]))

  compare_nodes(tree1.root, tree2.root)
  return differences


def cst_to_ast(tree: SyntaxTree, structural_kinds: set = None) -> SyntaxTree:
  """Remove structural tokens from CST"""
  if structural_kinds is None:
    structural_kinds = {"WHITESPACE", "COMMENT", "NEWLINE"}

  class ASTBuilder(TreeTransformer):
    def _transform_node(self, node: NodeView) -> Optional[Union[FrozenNode, FrozenToken]]:
      # Skip structural tokens
      if node.kind in structural_kinds:
        return None

      if node.is_token:
        return node._frozen

      # Transform children
      children = []
      for child in node.children:
        if transformed := self._transform_node(child):
          children.append(transformed)

      if not children:
        return None

      return FrozenNode(node.kind, tuple(children))

  return ASTBuilder().transform(tree)
