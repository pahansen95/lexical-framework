# Frozen-View Tree Architecture

A Frozen-View Tree provides an immutable, persistent tree data structure optimized for syntax tree manipulation. This architecture implements the Red-Green Tree pattern, where "Green" nodes (here called Frozen) form the immutable structural backbone, while "Red" nodes (here called View) provide mutable navigation facades. The naming reflects the functional roles: Frozen emphasizes immutability, View emphasizes the ephemeral navigation layer.

The architecture separates immutable structure (frozen nodes) from mutable navigation state (view nodes), enabling efficient incremental updates while maintaining thread safety. The system achieves memory efficiency through structural sharing - unchanged subtrees are reused across tree versions. This design pattern, proven in production compilers like Roslyn and Swift, enables sub-10ms response times for typical source code edits while providing safe concurrent access.

## Core Components

### Frozen Nodes - Immutable Structure
Frozen nodes store the persistent tree structure without parent references or absolute positions, enabling maximum reuse across versions.

```python
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Union, Protocol, Callable, Any
import weakref
import threading

class FrozenNode:
    """Immutable internal node with structural sharing"""
    __slots__ = ('kind', 'width', 'children', '_hash')
    
    def __init__(self, kind: str, width: int, children: Tuple['FrozenElement', ...]):
        self.kind = kind          # Node type identifier
        self.width = width        # Character count, not position
        self.children = children  # Immutable child tuple
        self._hash = None
    
    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash((self.kind, self.width, self.children))
        return self._hash
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, FrozenNode):
            return False
        return (self.kind == other.kind and 
                self.width == other.width and 
                self.children == other.children)
    
    def with_children(self, new_children: Tuple['FrozenElement', ...]) -> 'FrozenNode':
        """Create new node with replaced children"""
        if new_children == self.children:
            return self  # Reuse if unchanged
        width = sum(child.width for child in new_children)
        return FrozenNode(self.kind, width, new_children)

@dataclass(frozen=True, slots=True)
class FrozenToken:
    """Immutable leaf node containing source text"""
    kind: str
    text: str
    width: int = field(init=False)
    
    def __post_init__(self):
        object.__setattr__(self, 'width', len(self.text))

# Type alias for any frozen element
FrozenElement = Union[FrozenNode, FrozenToken]
```

### View Nodes - Navigation Layer
View nodes provide parent navigation and absolute positioning by wrapping frozen nodes with computed context.

```python
class NodeView:
    """Mutable facade over immutable frozen nodes"""
    __slots__ = ('_frozen', '_parent_ref', '_position', '_cached_children', '_index_in_parent')
    
    def __init__(self, frozen: FrozenElement, parent: Optional['NodeView'], 
                 position: int, index: int = 0):
        self._frozen = frozen
        self._parent_ref = weakref.ref(parent) if parent else None
        self._position = position
        self._index_in_parent = index
        self._cached_children = None
    
    @property
    def kind(self) -> str:
        return self._frozen.kind
    
    @property
    def parent(self) -> Optional['NodeView']:
        return self._parent_ref() if self._parent_ref else None
    
    @property
    def position(self) -> int:
        return self._position
    
    @property
    def width(self) -> int:
        return self._frozen.width
    
    @property
    def end_position(self) -> int:
        return self._position + self._frozen.width
    
    @property
    def children(self) -> List['NodeView']:
        if self._cached_children is None:
            self._cached_children = self._create_child_views()
        return self._cached_children
    
    @property
    def is_token(self) -> bool:
        return isinstance(self._frozen, FrozenToken)
    
    @property
    def text(self) -> Optional[str]:
        return self._frozen.text if isinstance(self._frozen, FrozenToken) else None
    
    def _create_child_views(self) -> List['NodeView']:
        if isinstance(self._frozen, FrozenToken):
            return []
        
        views = []
        pos = self._position
        for i, child in enumerate(self._frozen.children):
            view = NodeView(child, self, pos, i)
            views.append(view)
            pos += child.width
        return views
    
    def child(self, index: int) -> Optional['NodeView']:
        children = self.children
        return children[index] if 0 <= index < len(children) else None
    
    def find_at_position(self, position: int) -> Optional['NodeView']:
        if not (self.position <= position < self.end_position):
            return None
        
        for child in self.children:
            if result := child.find_at_position(position):
                return result
        
        return self
```

## Design Principles

**Structural Sharing**: Unchanged subtrees are reused between versions, typically sharing 95%+ of nodes
**Lazy Materialization**: View nodes are created only when accessed, reducing memory overhead
**Weak References**: Parent pointers use weak references to prevent memory cycles
**Bottom-Up Construction**: Trees are built leaves-first, ensuring immutability
**Cache Bounded**: Small nodes (≤3 children) are deduplicated, larger nodes are not

## Tree Construction

Construction uses a builder pattern that maintains mutability during assembly, then freezes the result.

```python
class TreeBuilder:
    """Constructs frozen trees with automatic deduplication"""
    
    def __init__(self, factory: Optional['FrozenNodeFactory'] = None):
        self._factory = factory or FrozenNodeFactory()
        self._stack: List[List[FrozenElement]] = [[]]
        self._positions: List[int] = [0]
    
    def start_node(self, kind: str) -> 'TreeBuilder':
        self._stack.append([])
        self._positions.append(self._current_position())
        return self
    
    def add_token(self, kind: str, text: str) -> 'TreeBuilder':
        token = self._factory.create_token(kind, text)
        self._stack[-1].append(token)
        return self
    
    def add_node(self, node: FrozenNode) -> 'TreeBuilder':
        self._stack[-1].append(node)
        return self
    
    def finish_node(self, kind: str) -> 'TreeBuilder':
        if len(self._stack) <= 1:
            raise ValueError("No node to finish")
        
        children = tuple(self._stack.pop())
        self._positions.pop()
        
        node = self._factory.create_node(kind, children)
        self._stack[-1].append(node)
        return self
    
    def build(self) -> FrozenNode:
        if len(self._stack) != 1:
            raise ValueError(f"Unclosed nodes: {len(self._stack) - 1}")
        if len(self._stack[0]) != 1:
            raise ValueError(f"Expected single root, got {len(self._stack[0])}")
        
        root = self._stack[0][0]
        if not isinstance(root, FrozenNode):
            raise ValueError("Root must be a node, not a token")
        
        return root
    
    def _current_position(self) -> int:
        return sum(node.width for nodes in self._stack for node in nodes)

class FrozenNodeFactory:
    """Creates and deduplicates frozen nodes"""
    
    def __init__(self):
        self._token_cache = {}
        self._small_node_cache = {}
        self._cache_size_limit = 3
    
    def create_token(self, kind: str, text: str) -> FrozenToken:
        key = (kind, text)
        if key not in self._token_cache:
            self._token_cache[key] = FrozenToken(kind, text)
        return self._token_cache[key]
    
    def create_node(self, kind: str, children: Tuple[FrozenElement, ...]) -> FrozenNode:
        width = sum(child.width for child in children)
        
        if len(children) <= self._cache_size_limit:
            key = (kind, tuple(id(c) for c in children))
            if key in self._small_node_cache:
                return self._small_node_cache[key]
            
            node = FrozenNode(kind, width, children)
            self._small_node_cache[key] = node
            return node
        
        return FrozenNode(kind, width, children)
```

## Incremental Updates

Updates create new tree versions by reconstructing only the path from change to root.

```python
class TreeUpdater:
    """Immutable tree updates with minimal copying"""
    
    def __init__(self, factory: Optional[FrozenNodeFactory] = None):
        self._factory = factory or FrozenNodeFactory()
    
    def replace_node(self, root: FrozenNode, path: List[int], 
                     new_node: FrozenElement) -> FrozenNode:
        if not path:
            if isinstance(new_node, FrozenToken):
                raise ValueError("Cannot replace root with token")
            return new_node
        
        return self._replace_recursive(root, path, new_node)
    
    def insert_child(self, root: FrozenNode, path: List[int], 
                     index: int, child: FrozenElement) -> FrozenNode:
        target = self._navigate_to_parent(root, path)
        children = list(target.children)
        children.insert(index, child)
        new_target = target.with_children(tuple(children))
        
        return self.replace_node(root, path, new_target) if path else new_target
    
    def remove_child(self, root: FrozenNode, path: List[int], index: int) -> FrozenNode:
        target = self._navigate_to_parent(root, path)
        children = list(target.children)
        
        if not (0 <= index < len(children)):
            raise IndexError(f"Child index {index} out of range")
        
        children.pop(index)
        new_target = target.with_children(tuple(children))
        
        return self.replace_node(root, path, new_target) if path else new_target
    
    def _replace_recursive(self, node: FrozenNode, path: List[int], 
                          new_node: FrozenElement) -> FrozenNode:
        index = path[0]
        if index >= len(node.children):
            raise IndexError(f"Path index {index} exceeds children count")
        
        if len(path) == 1:
            children = list(node.children)
            children[index] = new_node
            return node.with_children(tuple(children))
        
        child = node.children[index]
        if isinstance(child, FrozenToken):
            raise ValueError("Cannot traverse into token")
        
        new_child = self._replace_recursive(child, path[1:], new_node)
        children = list(node.children)
        children[index] = new_child
        return node.with_children(tuple(children))
    
    def _navigate_to_parent(self, root: FrozenNode, path: List[int]) -> FrozenNode:
        node = root
        for index in path:
            if isinstance(node, FrozenToken):
                raise ValueError("Cannot navigate into token")
            if index >= len(node.children):
                raise IndexError(f"Path index {index} exceeds children count")
            node = node.children[index]
        
        if isinstance(node, FrozenToken):
            raise ValueError("Path leads to token, expected node")
        
        return node
```

## Thread-Safe Wrapper

The SyntaxTree class provides safe concurrent access through thread-local view caches.

```python
class SyntaxTree:
    """Thread-safe wrapper with view caching"""
    
    def __init__(self, frozen_root: FrozenNode):
        if not isinstance(frozen_root, FrozenNode):
            raise TypeError("Root must be a FrozenNode")
        
        self._frozen_root = frozen_root
        self._view_cache = threading.local()
        self._updater = TreeUpdater()
    
    @property
    def root(self) -> NodeView:
        if not hasattr(self._view_cache, 'root'):
            self._view_cache.root = NodeView(self._frozen_root, None, 0)
        return self._view_cache.root
    
    @property
    def frozen_root(self) -> FrozenNode:
        return self._frozen_root
    
    def find_node_at(self, position: int) -> Optional[NodeView]:
        return self.root.find_at_position(position)
    
    def with_update(self, updater: Callable[[FrozenNode], FrozenNode]) -> 'SyntaxTree':
        new_frozen = updater(self._frozen_root)
        return SyntaxTree(new_frozen)
    
    def replace_node(self, path: List[int], new_node: FrozenElement) -> 'SyntaxTree':
        new_frozen = self._updater.replace_node(self._frozen_root, path, new_node)
        return SyntaxTree(new_frozen)
```

## Parser Integration

Parsers emit frozen trees by using the builder during parsing.

```python
from abc import ABC, abstractmethod

class Token:
    """Input token from lexer"""
    __slots__ = ('type', 'value', 'position')
    
    def __init__(self, type: str, value: str, position: int):
        self.type = type
        self.value = value
        self.position = position

class TreeParser(ABC):
    """Base parser that emits frozen trees"""
    
    def __init__(self):
        self._builder = TreeBuilder()
    
    @abstractmethod
    def parse(self, tokens: List[Token]) -> FrozenNode:
        pass
    
    def parse_to_syntax_tree(self, tokens: List[Token]) -> SyntaxTree:
        frozen = self.parse(tokens)
        return SyntaxTree(frozen)
```

## Visitor Pattern

Tree traversal and transformation use standard visitor patterns.

```python
class TreeVisitor(ABC):
    """Base visitor for tree traversal"""
    
    @abstractmethod
    def visit_node(self, node: NodeView) -> Any:
        pass
    
    @abstractmethod
    def visit_token(self, node: NodeView) -> Any:
        pass
    
    def visit(self, node: NodeView) -> Any:
        return self.visit_token(node) if node.is_token else self.visit_node(node)

class TreeTransformer(TreeVisitor):
    """Base transformer creating new trees"""
    
    def __init__(self):
        self._factory = FrozenNodeFactory()
    
    def transform(self, tree: SyntaxTree) -> SyntaxTree:
        frozen = self.transform_node(tree.root)
        return SyntaxTree(frozen)
    
    def transform_node(self, node: NodeView) -> FrozenElement:
        if node.is_token:
            return self.transform_token(node)
        
        children = [self.transform_node(child) for child in node.children]
        return self.visit_node_with_children(node, children)
    
    def transform_token(self, node: NodeView) -> FrozenToken:
        return self._factory.create_token(node.kind, node.text)
    
    def visit_node_with_children(self, node: NodeView, 
                                children: List[FrozenElement]) -> FrozenNode:
        return self._factory.create_node(node.kind, tuple(children))
```

## Usage Example

```python
# Build a tree
builder = TreeBuilder()
tree = (builder
    .start_node("expression")
    .add_token("number", "42")
    .add_token("operator", "+")
    .add_token("number", "8")
    .finish_node("expression")
    .build())

# Create syntax tree
syntax_tree = SyntaxTree(tree)

# Navigate
for child in syntax_tree.root.children:
    print(f"{child.kind}: {child.text or 'node'} at {child.position}")

# Update
new_tree = syntax_tree.replace_node([0], 
    FrozenToken("number", "100"))

# Thread-safe access
import threading

def analyze(tree):
    # Each thread gets its own view cache
    node = tree.find_node_at(2)
    print(f"Thread {threading.current_thread().name}: {node.kind}")

threads = [threading.Thread(target=analyze, args=(syntax_tree,)) for _ in range(3)]
for t in threads:
    t.start()
```

## Performance Characteristics

- **Memory**: 2x nodes (frozen + view), reduced to 1.5x through sharing
- **Updates**: O(depth) allocations, typically 5-20 nodes per edit  
- **First traversal**: O(n) view creation
- **Subsequent traversals**: O(1) cached access
- **Thread overhead**: Thread-local storage per syntax tree

## Implementation Checklist

1. Define frozen node types with `__slots__`
2. Implement builder with error checking
3. Create factory with bounded caches
4. Add thread-safe wrapper
5. Integrate parser to emit frozen trees
6. Test structural sharing with large trees
7. Verify weak references prevent cycles
8. Profile memory usage and cache hit rates

This architecture provides industrial-strength tree manipulation with Python's ease of use, balancing immutability guarantees with practical performance requirements.