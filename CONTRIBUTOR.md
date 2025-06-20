# Contributor's Guide

> This document describes expectations of developers, provides development frameworks, establishes directives on coding conventions, offers opinionated recommendations on developer environments, and concludes with further reading for contributor success.

## What is Good?

> *“Simplicity is prerequisite for reliability.” — Edsger W. Dijkstra*

Every healthy codebase shares a small set of enduring qualities.  This guide opens with them so that every contributor—from first‑time committer to long‑term maintainer—starts with the same mental model and vocabulary.

### 1 Correctness is non‑negotiable

Our first duty is to ship behaviour that faithfully matches user‑visible intent and internal contracts. Tests, static checks and—where stakes demand—formal proofs are the guard‑rails.  If the behaviour is wrong, nothing else buys redemption.

### 2 Simplicity beats cleverness

We seek the *least* complicated design that solves today’s need while leaving tomorrow unobstructed. Prefer clear data structures and straight‑line logic to intricate abstractions; embrace YAGNI and delete dead paths early.

### 3 Readability enables change

Code is a long‑lived conversation between authors. Names should reveal intent; control flow should read top‑to‑bottom; modules should have single, obvious responsibilities. If an unfamiliar engineer cannot reason about a unit in minutes, refactor or document until they can.

### 4 Fitness for purpose

Quality lives in context: throughput matters in services, determinism in analytics, robustness in safety‑critical paths. Meet the non‑functional constraints that matter—and prove it with measurements, not intuition.

### 5 Sustainable maintainability

Every PR must make the future easier, never harder. We budget time for refactoring, guard against technical debt, and keep build, test and deploy feedback loops fast. A patch that adds value today at the cost of tomorrow’s velocity is not “done”.

---

### How to apply this model in practice

| When you…            | Ask yourself…                                                |
| -------------------- | ------------------------------------------------------------ |
| Design a feature     | *Is the simplest correct design obvious?  What will it look like after three more iterations?* |
| Review code          | *Does this change shrink or grow complexity?  Could I maintain it six months from now?* |
| Optimise performance | *Are we optimising the 3 % of code that matters?  Can we isolate the tricky bits behind a clear façade?* |
| Take a shortcut      | *What debt are we incurring?  When—and how—will we pay it off?* |

**Key expectation:**  *If a contribution erodes any pillar above, it requires a clear, written justification and a plan to restore balance.*

Embodying these principles keeps the codebase pliable, reliable and a pleasure to work with—today and for the next generation of contributors.

---

## How to Develop Good

> *“Process without principles is bureaucracy; principles without process is wishful thinking.” — Mark Schwartz*

To write "good" code all you need to do is:

1. Think First
2. Code Second
3. Continuously Iterate

We establish a simple framework, The **A · I · O loop**, to guide developers: 

* **Articulate** *what* we’re doing and *why* before writing any code.
* **Implement** your vision as models, source code & tests in equal measure.
* **Observe** runtime behavior to understand the gap & iterate accordingly.

Spend roughly equal time articulating & implementing. Automate Observations to quickly iterate.

---

### **A · I · O Loop Procedures**

#### Articulate — *think first*

1. **Discover** – Capture intent; describe your mental models plainly; record user's desired outcomes & expectations of behavior.
2. **Constrain** – Establish (or re-use) a common vernacular; define the extents of your problem space; state your predicates & baseline assumptions.
3. **Architect** – Identify the structure of data & procedural flow of behaviors; understand pre-established patterns and paradigms; posit questions on known unknowns.

Use this process to explore your understanding of the problem & how it maps to your development environment. You are formulating mental models. Spend equal time Articulating as you do Implementing. You're done when you feel like you're hitting diminishing returns (e.g. splitting hairs, chasing rabbits, or talking philosophy).

#### Implement — *code second*

4. **Model** – Write structural & behavioral specifications; formally or otherwise.
5. **Code** – Build a solution that matches your mental models.
6. **Test** – Attempt to falsify behaviors & structures of the code.

Use this process to materialize & validate your mental models. Source code is only one piece of the puzzle. Don't get hung up on premature optimizations or perfection; mark anything that "smells", so we know to come back to it later. Focus on mapping your mental models to executable software. Spend equal time Implementing as you do Articulating. You're done when you feel like you're hitting diminishing returns (e.g. refactoring for style, playing golf or bogged in technical debt).

#### Observe — *continuously iterate*

7. **Measure** – Record & analyze logs, metrics & profiles to determine real world behavior.
8. **Analyze** – Conduct Gap Analysis; compare the observed behavior with your recorded intent.
9. **Iterate** – Measure the error & describe next steps.

Use this process to inform what comes next. Favor automation & fast feedback to increase the time you spend articulating & implementing. If the gap is conceptual, loop to *Articulate*; if it’s execution, loop to *Implement*. Iterate until you have "good" code. If you feel the process isn't working, then challenge your approach. If accrued technical debt is a burden, then pay it down. If there is no gap, then congratulations, you're done... for now.

## Coding Conventions

Python code should be correct, simple, and performant. These conventions establish patterns proven in production systems, balancing software engineering principles with Python's pragmatic culture.

### Core Philosophy

Write straightforward code that leverages Python's strengths. Complexity should emerge from the problem domain, not the implementation approach. Every pattern must earn its place through measurable benefit.

### Data Structure Selection

Choose data structures based on access patterns and performance characteristics. Python's built-in types are highly optimized and should be preferred over custom implementations.

**Access Pattern Guidelines**:
- Use `dict` for O(1) key-based lookups
- Use `set` for O(1) membership testing
- Use `list` for sequential access and indexing
- Use `deque` for queue operations (append/popleft)
- Use `tuple` for immutable sequences
- Use `dataclass` with `__slots__` for structured data

```python
class TokenCache:
    def __init__(self):
        self._by_type = {}          # Quick lookup by type
        self._ordered = []          # Maintain insertion order
        self._seen = set()          # Fast duplicate detection
```

### State Management

Prefer immutable interfaces with efficient internal implementations. Use `__slots__` to reduce memory overhead by 30-40% on frequently instantiated classes.

**Immutable API Pattern**:
```python
@dataclass
class Position:
    """Immutable position in source text."""
    __slots__ = ('line', 'column', 'offset')
    line: int
    column: int
    offset: int
    
    def advance(self, text: str) -> 'Position':
        # Return new instance for public API
        if text == '\n':
            return Position(self.line + 1, 1, self.offset + 1)
        return Position(self.line, self.column + 1, self.offset + 1)
```

**Internal Mutation Pattern**:
```python
class _StreamState:
    """Mutable internal state for performance."""
    __slots__ = ('tokens', 'position')
    
    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0
```

### Error Handling

Validate inputs at system boundaries. Trust internal state after validation. Let Python's built-in exceptions communicate failures naturally.

**Boundary Validation**:
```python
def parse(text: str) -> AST:
    # Validate once at entry
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__}")
    
    # Internal functions trust validated input
    tokens = _tokenize(text)
    return _build_ast(tokens)
```

**Natural Error Propagation**:
```python
def process_config(data: dict) -> Config:
    # Let KeyError naturally describe missing keys
    return Config(
        name=data['name'],
        options=data.get('options', {})
    )
```

### Type Annotations

Apply type hints to public APIs and data structures. Use gradual typing to balance clarity with flexibility.

**Annotation Strategy:**

Start with high-impact patterns and stop when types add more complexity than value. Target 80% coverage on public interfaces, not 100% everywhere.

**Priority Order:**
1. Public function signatures
2. Data structures (dataclasses, NamedTuples)
3. Return types before parameter types
4. Complex business logic functions
5. Skip internal implementation details

**Public API Typing:**
```python
from typing import Optional, List, Dict, Protocol

def tokenize(text: str) -> List[Token]:
    """Always type public interfaces completely."""
    return list(_generate_tokens(text))

def _generate_tokens(text):  # Internal: types optional
    # Implementation without type hints is fine
    for match in pattern.finditer(text):
        yield Token(match.group(), match.start())
```

**Data Structure Typing:**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParseResult:
    """Type containers for clarity and validation."""
    ast: Node
    errors: List[ParseError]
    metadata: Optional[Dict[str, Any]] = None
```

**Protocol Definitions:**
```python
class Parseable(Protocol):
    """Define interfaces without inheritance."""
    def parse(self) -> Result: ...
    
# Accept protocol, not concrete type
def process(item: Parseable) -> None:
    result = item.parse()
```

**Pragmatic Escape Hatches:**
```python
from typing import Any, cast

# Use Any when types get too complex
ComplexType = Dict[str, Any]  # Better than 5-level nested type

# Cast when you know better than the checker
config = cast(Config, json.loads(data))  # Validated elsewhere

# Type ignore for dynamic patterns
setattr(obj, name, value)  # type: ignore[attr-defined]
```

**Generic Usage Guidelines:**

Use Generics only when they clarify intent. Prefer simple types over complex abstractions.

```python
# Good: Clear value in reusable container
T = TypeVar('T')
class Cache(Generic[T]):
    def get(self, key: str) -> Optional[T]: ...

# Bad: Over-abstracted
K = TypeVar('K', bound=Hashable)
V = TypeVar('V')
class AbstractCache(Generic[K, V], Protocol[K, V]): ...

# Better: Simple and clear
class Cache:
    def get(self, key: str) -> Optional[dict]: ...
```

**Type Annotation Anti-Patterns:**

```python
# Over-specified internal function
def _helper(
    data: Dict[str, Union[str, int, List[str]]], 
    flags: Optional[Dict[str, bool]] = None
) -> Tuple[bool, Optional[str]]:
    # Too much detail for private function

# Complex nested generics
Parser = Callable[[List[Token]], Result[AST[Node[T]]]]

# Runtime type enforcement
def process(items: List[int]):
    if not all(isinstance(i, int) for i in items):
        raise TypeError  # Don't do this
```

**Guidelines:**

1. **Type public interfaces** - Help users understand your API
2. **Skip private details** - Don't annotate every internal variable
3. **Use Any liberally** - When precision adds no value
4. **Avoid runtime validation** - Types are for development, not execution
5. **Keep generics simple** - One type parameter is usually enough
6. **Accept gradual coverage** - 80% typed is better than 100% convoluted

**Tooling Configuration:**
```python
# mypy.ini or pyproject.toml
[mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
# Don't require 100% coverage
disallow_untyped_defs = false
# Allow gradual adoption
disallow_any_expr = false
```

### Performance Patterns

Write standard patterns that Python can optimize. Profile before optimizing. Accept trade-offs between performance and other qualities.

**Performance Hierarchy:**

1. **Algorithmic Efficiency** - O(n) beats O(n²) regardless of implementation
2. **Built-in Operations** - Leverage C-powered operations over Python loops
3. **Memory Efficiency** - Stream data rather than loading everything
4. **Targeted Optimization** - Profile hotspots, optimize only what matters

**Memory Management:**

Choose data structures based on measured impact:

```python
# Standard class: 64 bytes per instance
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# With __slots__: 40 bytes per instance (37% reduction)
class Point:
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x = x
        self.y = y

# For millions of instances, the difference matters
```

**Immutability Trade-offs:**

Frozen dataclasses cost 38% more to instantiate. Use immutability for correctness at API boundaries, not for performance:

```python
# API boundary: immutability prevents bugs
@dataclass(frozen=True)
class APIResponse:
    status: int
    data: dict

# Internal processing: mutability for speed
@dataclass
class ProcessingBuffer:
    items: list
    position: int
```

**Concurrency Patterns:**

Work with Python's Global Interpreter Lock (GIL), not against it:

```python
# I/O-bound: Use asyncio for concurrent requests
async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(*[fetch(session, url) for url in urls])

# CPU-bound: Use process pools
def parallel_compute(data):
    with multiprocessing.Pool() as pool:
        return pool.map(expensive_computation, data)

# Threading only helps for I/O waiting, not computation
```

**Built-in Optimizations:**

Prefer operations that run in C:

```python
# Fast: Built-in operations
text = ''.join(parts)                    # Not: text += part
filtered = [x for x in items if valid(x)]  # Not: manual append loop
total = sum(numbers)                     # Not: manual accumulation
found = any(check(x) for x in items)     # Not: manual break loop

# Fast: Collection lookups
lookups = set(items)                     # O(1) membership testing
mapping = dict(pairs)                    # O(1) key access
```

**Generator Patterns:**

Stream processing for memory efficiency:

```python
# Memory efficient: Process without loading all
def process_large_file(path):
    with open(path) as f:
        for line in f:  # One line at a time
            if result := process_line(line):
                yield result

# Chain generators for pipeline processing
cleaned = (clean(line) for line in raw_lines)
parsed = (parse(line) for line in cleaned if valid(line))
results = list(parsed)  # Materialize only at end
```

**Profiling Strategy:**

Measure before optimizing:

```python
# Development: Use cProfile for detailed analysis
python -m cProfile -s cumulative script.py

# Production: Use sampling profilers with minimal overhead
# py-spy (external): ~0% overhead
# Austin (external): ~0% overhead

# Quick timing for specific operations
from time import perf_counter
start = perf_counter()
result = operation()
duration = perf_counter() - start
```

**Scale-Aware Optimization:**

Different scales require different approaches:

- **< 1MB data**: Use standard Python, optimize algorithms only
- **< 100MB data**: Add caching, consider data structure choices
- **< 1GB data**: Stream processing, optimize memory layout
- **> 1GB data**: Consider NumPy/Pandas or external processing

**Performance Anti-Patterns:**

```python
# Don't micro-optimize Python
x = x + 1  # This is fine, don't use x += 1 for "speed"

# Don't fight the GIL with threads
threads = [Thread(target=cpu_task) for _ in range(8)]  # Won't parallelize

# Don't implement what exists
def my_sort(items): ...  # Just use sorted()

# Don't cache everything
@lru_cache(maxsize=None)  # Unbounded memory growth
```

**When Python Isn't Enough:**

Accept when to use other tools:

- **Numerical computation**: NumPy/SciPy (C/Fortran backends)
- **Data processing**: Pandas (Cython optimized)
- **Machine learning**: PyTorch/TensorFlow (GPU acceleration)
- **Critical loops**: Cython or C extension
- **System-level performance**: Rewrite service in Rust/Go

**Guidelines:**

1. **Write clear code first** - Modern Python rewards standard patterns
2. **Profile before optimizing** - Measure actual bottlenecks
3. **Optimize algorithms** - Better complexity beats micro-optimization
4. **Use built-ins** - They run in C and release the GIL
5. **Accept trade-offs** - Choose between speed, memory, and maintainability
6. **Know when to delegate** - Python as orchestrator, not number cruncher

### Code Organization

Structure code to minimize complexity. Prefer modules and functions over classes. Keep inheritance shallow.

**Module Design Principles:**

1. **Single purpose** - Each module encapsulates one coherent capability
2. **Explicit dependencies** - Import what you need, export what others need
3. **No side effects on import** - Initialization happens in functions, not at module level
4. **Clear public API** - Use `__all__` and underscore prefixes

**When to Use Modules + Functions:**

Prefer module-level functions for:

- **Stateless operations** - Pure transformations with no persistent state
- **Algorithms** - Computational procedures that don't need object identity
- **Utilities** - Shared helpers used across the codebase
- **Simple workflows** - Linear processing without complex state management

```python
# transform.py - Stateless operations
def normalize_text(text: str) -> str:
    return ' '.join(text.lower().split())

def tokenize(text: str) -> List[str]:
    return normalize_text(text).split()
```

**When to Use Classes:**

Use classes only when you need:

- **Stateful objects** - Managing mutable state across method calls
- **Resource management** - Context managers for cleanup (`__enter__`/`__exit__`)
- **Polymorphism** - Multiple implementations of the same interface
- **Data + behavior** - When operations are tightly coupled to specific data

```python
# Good: Resource management
class DatabaseConnection:
    def __enter__(self):
        self._conn = connect()
        return self._conn
    
    def __exit__(self, *args):
        self._conn.close()
```

**Module Structure Pattern:**

```python
# feature.py - Standard module layout

# 1. Imports
from typing import Optional
from .types import Request, Response

# 2. Constants
DEFAULT_TIMEOUT = 30

# 3. Public API
def process_request(request: Request) -> Response:
    """Main entry point."""
    validated = _validate(request)
    return _execute(validated)

# 4. Internal implementation (underscore prefix)
def _validate(request: Request) -> Request:
    # Implementation
    pass

# 5. Explicit exports
__all__ = ['process_request', 'DEFAULT_TIMEOUT']
```

**Critical Anti-Patterns:**

**Hidden Global State**

```python
# BAD: Implicit mutation
_cache = {}
def get_data(key):
    _cache[key] = fetch(key)  # Hidden side effect!

# GOOD: Explicit state management
class DataCache:
    def get_data(self, key):
        self._cache[key] = fetch(key)
```

**Import Side Effects**

```python
# BAD: Runs on import
db = connect_to_database()  # Fails if DB is down!

# GOOD: Lazy initialization
_db = None
def get_db():
    global _db
    if _db is None:
        _db = connect_to_database()
    return _db
```

**Module Coupling**

```python
# BAD: Reaching into internals
from other_module import _internal_state

# GOOD: Use public APIs
from other_module import update_state
```

**State Management Patterns:**

When modules need state, make it explicit:

```python
# Configuration
_config = {}

def configure(**options):
    """Explicit configuration API."""
    _config.update(options)

# Thread-safe context
import contextvars
current_user = contextvars.ContextVar('user')

# Singleton when necessary
_instance = None
def get_instance():
    global _instance
    if _instance is None:
        _instance = create_instance()
    return _instance
```

**Package Structure and Maintenance:**

Create packages only when a module grows beyond ~300 lines or needs internal organization. Keep hierarchies shallow (2-3 levels maximum).

**Package Design Principles:**

1. **Single domain** - Each package owns one area of functionality
2. **Clear boundaries** - No circular dependencies between packages
3. **Explicit exports** - `__init__.py` defines the public API
4. **Independent testing** - Each package testable in isolation

**Standard Package Layout:**

```
feature/
  __init__.py      # Public API exports only
  core.py          # Main implementation
  types.py         # Type definitions
  errors.py        # Custom exceptions
  _internal.py     # Private helpers (underscore prefix)
  
tests/
  test_feature.py  # Mirrors package structure
```

***\*init\**.py Pattern:**

```python
"""Feature package for X functionality."""

from .core import process, validate
from .types import Request, Response
from .errors import FeatureError

__all__ = [
    # Public functions
    'process',
    'validate',
    # Public types
    'Request', 
    'Response',
    # Public exceptions
    'FeatureError',
]
```

**Package Anti-Patterns:**

**Deep Nesting**

```python
# BAD: Too many levels
company/platform/services/auth/handlers/oauth/google.py

# GOOD: Flat and focused
auth/oauth.py
auth/handlers.py
```

**Circular Dependencies**

```python
# BAD: Packages depend on each other
# users/__init__.py
from ..orders import Order  # Orders depends on User!

# GOOD: Extract shared types
# models/types.py
class User: ...
class Order: ...

# users/__init__.py
from ..models.types import User
```

**API Sprawl**

```python
# BAD: Everything exported
from .internals import *
from .helpers import *
from .utils import *

# GOOD: Deliberate exports
__all__ = ['parse', 'ParseError']  # Only what clients need
```

**Package Evolution Guidelines:**

1. **Start as module** - Don't create packages preemptively
2. **Extract when needed** - When module exceeds ~300 lines or has clear sub-components
3. **Maintain compatibility** - Use deprecation warnings before removing APIs
4. **Periodic cleanup** - Review and consolidate APIs annually

**Inter-package Communication:**

```python
# Define clear interfaces between packages
# auth/interface.py
from typing import Protocol

class Authenticator(Protocol):
    def authenticate(self, token: str) -> User: ...

# webapp/app.py
def create_app(auth: Authenticator):
    """Accept interface, not concrete package."""
    pass
```

**Summary:** Start with functions in modules. Graduate to packages when modules grow beyond a single responsibility. Keep packages shallow, exports explicit, and boundaries clear. Refactor periodically to prevent API bloat.

### Observability

Build in lightweight debugging and monitoring from the start. Use zero-cost instrumentation that disappears when disabled.

**Zero-Cost Principle:**

Observability must have near-zero overhead when disabled. A single boolean check should short-circuit all instrumentation.

```python
import instrumentation

# Fast path when no handlers attached
instrumentation.emit('token.match', 'IDENTIFIER')  # Returns immediately if disabled

# Attach handler only when debugging
if DEBUG:
    instrumentation.attach(instrumentation.create_print_handler())
```

**Event Emission Pattern:**

Emit structured events at key points. Let handlers decide what to consume.

```python
def parse_expression(tokens):
    # Minimal emission - just type and value
    instrumentation.emit('rule.enter', 'expression')
    
    try:
        # Parse logic here
        result = self._parse_expr(tokens)
        instrumentation.emit('rule.exit', 'expression', success=True)
        return result
    except ParseError as e:
        instrumentation.emit('rule.exit', 'expression', success=False, error=str(e))
        raise
```

**Context Propagation:**

Use context managers for automatic event enrichment:

```python
# Parse depth tracked automatically
with instrumentation.increment_depth():
    with instrumentation.parsing_rule('function_def'):
        # Events here include depth=1, rule='function_def'
        instrumentation.emit('parse.start', 'parsing function')
        
# Timing critical operations
with instrumentation.timed('parse.duration'):
    ast = parser.parse(source)
```

**Selective Activation:**

Enable only what you need for targeted debugging:

```python
# Category-based filtering
instrumentation.enable_categories('lex')     # Only lexer events
instrumentation.disable_categories('token')  # Too noisy

# Production sampling (1% of operations)
if PRODUCTION:
    handler = instrumentation.create_sampling_handler(
        0.01, 
        instrumentation.create_metrics_handler()[0]
    )
    instrumentation.attach(handler)
```

**Handler Patterns:**

Choose handlers based on use case:

```python
# Development: Print to console
instrumentation.attach(
    instrumentation.create_print_handler(prefix='parse.')
)

# Debugging: Ring buffer for post-mortem
buffer_handler, get_events = instrumentation.create_ring_buffer(1000)
instrumentation.attach(buffer_handler)
# On error, examine recent events
if error:
    recent = get_events()

# Production: Metrics only
metrics_handler, get_metrics = instrumentation.create_metrics_handler()
instrumentation.attach(metrics_handler)
# Periodic reporting
print(get_metrics())  # {'counters': {...}, 'durations': {...}}
```

**Performance Guidelines:**

```python
# Conditional emission for expensive operations
if instrumentation.get_handler_count() > 0:
    # Only compute expensive debug info if someone is listening
    debug_info = compute_ast_statistics(ast)
    instrumentation.emit('ast.stats', debug_info)

# Lazy message formatting
instrumentation.emit('parse.complete', 
    lambda: f"Parsed {node_count} nodes in {duration}ms"
)

# Bounded resource usage
# Ring buffer automatically limits memory
# File handler can rotate logs
# Metrics aggregate without storing all events
```

**Integration Pattern:**

```python
class Parser:
    def __init__(self, trace=False):
        if trace:
            # Development mode with full tracing
            instrumentation.attach(
                instrumentation.create_print_handler()
            )
        
    def parse(self, source):
        with instrumentation.set_context(file=source.name):
            # All events include file context
            return self._parse_impl(source)
    
    def get_metrics(self):
        # Expose accumulated metrics
        return self._metrics_handler[1]() if self._metrics_handler else {}
```

**Anti-Patterns:**

```python
# Don't format eagerly
instrumentation.emit('data', f"Value: {expensive_repr(obj)}")  # Bad

# Don't emit in tight loops without guards
for byte in megabytes:
    instrumentation.emit('byte', byte)  # Performance killer

# Don't create handlers in hot paths
def process():
    handler = create_handler()  # Allocates every time
    instrumentation.attach(handler)
```

**Guidelines:**

1. **Default to off** - No handlers attached in normal operation
2. **Emit sparingly** - Key transitions and boundaries only
3. **Guard expensive work** - Check handler count before complex computations
4. **Use categories** - Allow granular debugging without overwhelming detail
5. **Bound resources** - Ring buffers and sampling prevent memory issues
6. **Measure impact** - Profile with instrumentation on/off to verify zero-cost

### Testing Patterns

Write tests that verify behavior, not implementation. Focus on boundary conditions and integration points.

**Behavioral Testing**:
```python
def test_parser_handles_empty_input():
    # Test behavior, not internals
    result = parse("")
    assert result == EmptyAST()

def test_parser_validates_input():
    # Verify boundary validation
    with pytest.raises(TypeError, match="Expected str"):
        parse(123)
```

### Convention Summary

1. **Choose appropriate data structures** - Use built-ins for their optimized performance
2. **Validate at boundaries** - Check inputs once, trust internal state
3. **Type public interfaces** - Document contracts without runtime overhead
4. **Write boring code** - Standard patterns enable Python optimizations
5. **Organize simply** - Minimize layers and indirection
6. **Debug efficiently** - Lazy logging and compile-time assertions
7. **Test behavior** - Verify what code does, not how

These conventions produce Python code that is both correct and performant, achieving software engineering goals through Python-specific mechanisms.

## Environment & Tooling

> Fill in as necessary

## Further Reading

> Fill in as necessary