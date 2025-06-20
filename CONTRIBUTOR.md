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

Python code must be correct, simple, and performant. These conventions are requirements for all contributions. Violations block merge approval.

Code organization follows five mandatory layers:
- **Data Layer**: Required structures and state patterns
- **Contract Layer**: Mandatory interfaces and error handling
- **Organization Layer**: Required module and package structure
- **Performance Layer**: Required optimization approaches
- **Operations Layer**: Mandatory debugging and maintenance patterns

### Core Requirements

Write code that leverages Python's built-in optimizations. Never introduce complexity without measured benefit. All patterns must demonstrate quantifiable improvement.

**The Boundary Principle**: Always validate inputs at system boundaries. Never perform redundant validation within trusted boundaries. This principle is mandatory at: API entry points, module interfaces, external data ingestion, and debug instrumentation.

### Data Layer: Required Structures and State

The Data Layer establishes fundamental patterns for data representation and state management in Python programs. It defines how information flows through the system while maintaining correctness and performance guarantees.

This layer operates on the principle that proper data structure selection eliminates entire classes of bugs while enabling optimal performance. Each built-in type provides specific algorithmic guarantees - dict offers O(1) lookups, set provides O(1) membership testing, and deque enables efficient queue operations. State management patterns distinguish between immutable public interfaces that ensure predictable behavior and mutable internal implementations that maximize performance.

Core principles:
- Structure determines available operations
- Immutability at boundaries prevents action at a distance
- Internal mutation enables necessary optimizations
- Memory layout impacts cache performance

The mental model: Choose representations that make correct behavior natural and incorrect behavior impossible.

#### Requirements

All code must follow these data structure and state management rules.

#### Mandatory Patterns

**Required Data Structure Selection**:
```python
# MUST use for O(1) operations
lookups = {}            # Key-based access
members = set()         # Membership testing
queue = deque()         # FIFO operations

# MUST use for sequential access
items = []              # Indexed access
immutable = tuple()     # Read-only sequences

# MUST use for structured data
@dataclass
class Config:
    __slots__ = ('host', 'port')  # Required for >1000 instances
    host: str
    port: int
```

**Required State Management**:
```python
from typing import Final

# Public APIs MUST use Final annotations for immutability
@dataclass
class Position:
    """Immutable position enforced by static analysis."""
    __slots__ = ('line', 'column', 'offset')  # Required for memory efficiency
    line: Final[int]
    column: Final[int]
    offset: Final[int]
    
    def advance(self, text: str) -> 'Position':
        # MUST return new instance
        if text == '\n':
            return Position(self.line + 1, 1, self.offset + 1)
        return Position(self.line, self.column + 1, self.offset + 1)

# REQUIRED: Use typing.Final for zero-cost immutability
# Static type checkers enforce Final at development time
# No runtime overhead in production

# Optional debug-only protection for critical APIs
@dataclass(frozen=__debug__)  # Frozen only in development
class CriticalConfig:
    __slots__ = ('host', 'port')
    host: Final[str]
    port: Final[int]

# Internal state MAY mutate for performance
class _StreamState:
    __slots__ = ('tokens', 'position')  # Required slots
    
    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0  # Allowed: internal mutation
```

#### Forbidden Patterns

```python
# NEVER use mutable defaults
def process(items=[]):  # FORBIDDEN

# NEVER use dict where set suffices
seen = {}  # WRONG if only testing membership
seen = set()  # CORRECT

# NEVER implement built-in functionality
class MyQueue:  # FORBIDDEN - use collections.deque
```

### Contract Layer: Required Interfaces and Errors

The Contract Layer establishes explicit agreements between system components through type annotations, validation patterns, and error handling strategies. It ensures that component interactions are well-defined, verifiable, and fail predictably when violated.

This layer implements the boundary principle - comprehensive validation at system entry points followed by trusted operation within validated contexts. Type annotations serve as machine-checkable documentation while exceptions communicate contract violations naturally. The approach balances safety with performance by avoiding redundant checks once data enters the trusted interior.

Key concepts:
- Types as executable documentation
- Validation at boundaries only
- Natural error propagation
- Gradual typing for practical adoption

The mental model: Define clear contracts, enforce them at boundaries, then operate with confidence in the validated environment.

#### Requirements

Type annotations and validation are mandatory at all boundaries.

### Mandatory Patterns

**Required Boundary Validation**:
```python
from typing import Optional, List, Protocol

def parse(text: str) -> AST:  # Type annotations REQUIRED
    # MUST validate at entry
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__}")
    
    # Internal functions need NOT validate
    tokens = _tokenize(text)
    return _build_ast(tokens)

# MUST use protocols for duck typing
class Parseable(Protocol):
    def parse(self) -> Result: ...
```

**Required Type Coverage**:
- 100% of public API parameters and returns
- 100% of dataclass fields
- 80% minimum of internal functions that cross module boundaries
- 0% required for single-use private helpers

**Required Error Patterns**:
```python
# MUST let errors propagate naturally
def process_config(data: dict) -> Config:
    # Let KeyError communicate the problem
    return Config(
        name=data['name'],  # Required key
        options=data.get('options', {})  # Optional with default
    )

# MUST NOT catch and re-raise without adding value
try:
    process()
except Exception as e:
    raise  # CORRECT: preserves stack trace
```

### Forbidden Patterns

```python
# NEVER enforce types at runtime
if not isinstance(arg, int):  # FORBIDDEN except at boundaries
    raise TypeError

# NEVER use complex generics
T = TypeVar('T', bound=Hashable)
Parser = Callable[[List[Token]], Result[AST[Node[T]]]]  # FORBIDDEN

# NEVER annotate if it adds no value
def _helper(x: Any) -> Any:  # Just omit annotations
```

### Organization Layer: Required Module Structure

The Organization Layer defines how code is structured into modules and packages to maximize clarity and minimize coupling. It establishes patterns for evolving from simple scripts to complex systems while maintaining navigability and clear dependency relationships.

This layer follows the principle of progressive complexity - start with functions in modules, graduate to classes when state management is needed, and create packages only when modules exceed their single responsibility. Clear boundaries between components are enforced through explicit exports and naming conventions. The approach prevents premature abstraction while supporting natural growth.

Organizational principles:
- Single responsibility per module
- Explicit public interfaces via __all__
- Shallow hierarchies (3 levels maximum)
- Dependencies flow in one direction

The mental model: Code organization should reflect problem domain structure, not implementation details. Grow complexity only in response to actual needs.

#### Requirements

Code organization must follow these patterns to ensure maintainability.

#### Mandatory Patterns

**Required Module Structure**:
```python
# feature.py - MUST follow this order

# 1. Module docstring (required)
"""Feature X provides Y functionality."""

# 2. Imports (grouped and ordered)
import standard_library
import third_party
from . import local_modules

# 3. Module constants
DEFAULT_TIMEOUT = 30  # UPPERCASE required

# 4. Public API
def public_function() -> Result:
    """Docstring required for public functions."""
    pass

# 5. Private implementation (underscore prefix required)
def _private_helper():
    pass

# 6. Explicit exports (required)
__all__ = ['public_function', 'DEFAULT_TIMEOUT']
```

**Required Package Evolution**:
```python
# MUST start as single module
auth.py

# MUST convert to package when >300 lines
auth/
  __init__.py      # Public exports only
  core.py          # Implementation
  types.py         # Type definitions
  _internal.py     # Private (underscore required)
```

### Forbidden Patterns

```python
# NEVER create deep hierarchies (>3 levels)
company/platform/services/auth/handlers/  # FORBIDDEN

# NEVER use star imports
from .module import *  # FORBIDDEN

# NEVER export private members
__all__ = ['_internal_func']  # FORBIDDEN

# NEVER create circular imports
# a.py: from .b import x
# b.py: from .a import y  # FORBIDDEN
```

### Performance Layer: Required Optimization Approach

The Performance Layer establishes a systematic approach to optimization based on measurement and Python-specific characteristics. It defines a strict hierarchy for performance improvements that prevents premature optimization while ensuring efficient resource utilization.

This layer operates on the principle that algorithmic improvements dominate implementation details, and built-in operations leverage C-level optimizations unavailable to pure Python code. The Global Interpreter Lock (GIL) fundamentally shapes concurrency strategies - asyncio for I/O-bound work, multiprocessing for CPU-bound tasks. All optimization decisions must be driven by profiling data rather than intuition.

Performance hierarchy:
- Algorithm selection (O(n) vs O(n²))
- Built-in operations (C-level speed)
- Memory layout (__slots__, data locality)
- Concurrency model (async vs processes)

The mental model: Measure first, optimize the bottleneck, leverage Python's strengths. Accept when Python isn't the right tool rather than contorting the language.

#### Requirements

Performance optimization must follow this strict hierarchy. Never skip levels.

#### Mandatory Patterns

**Required Optimization Order**:
```python
# 1. MUST optimize algorithms first
# Bad: O(n²)
for item in items:
    if item in list_items:  # O(n) lookup
        process(item)

# Good: O(n)
item_set = set(list_items)  # O(n) setup
for item in items:
    if item in item_set:    # O(1) lookup
        process(item)

# 2. MUST use built-in operations
text = ''.join(parts)       # REQUIRED over += loop
total = sum(numbers)        # REQUIRED over manual loop
found = any(condition(x) for x in items)  # Short-circuits

# 3. MUST use __slots__ for frequently instantiated classes
class Token:
    __slots__ = ('type', 'value', 'position')  # Saves 37% memory
    
# 4. MUST use appropriate concurrency
# I/O-bound: asyncio required
async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(
            *[fetch(session, url) for url in urls]
        )

# CPU-bound: multiprocessing required
def parallel_compute(data):
    with multiprocessing.Pool() as pool:
        return pool.map(compute, data)
```

**Required Profiling**:
```python
# MUST profile before optimization
# Acceptable profiling methods:
# - cProfile for development
# - py-spy for production (0% overhead)
# - perf_counter() for specific operations

# MUST include measurement in optimization PRs
# Before: 3.4s (provide profiler output)
# After: 1.2s (provide profiler output)
# Method: <specific change made>
```

**Required Scale-Based Decisions**:
```python
# MUST choose architecture based on data scale
if data_size < 1_000_000:      # < 1MB: Standard Python
    process_simple(data)
elif data_size < 100_000_000:  # < 100MB: Add caching  
    process_with_cache(data)
elif data_size < 1_000_000_000: # < 1GB: Stream processing
    process_streaming(data)
else:                           # > 1GB: Specialized tools
    # MUST use NumPy/Pandas/Polars for data >1GB
    raise ValueError("Use specialized tools for data >1GB")
```

### Forbidden Patterns

```python
# NEVER micro-optimize without profiling
x = x + 1  # This is fine
x += 1     # Don't change for "performance"

# NEVER use threads for CPU-bound work
Thread(target=cpu_intensive_task)  # FORBIDDEN - use Process

# NEVER implement premature caching
@lru_cache(maxsize=None)  # FORBIDDEN without proven need
def simple_function(x):
    return x * 2
```

### Operations Layer: Required Debug and Maintenance

The Operations Layer provides comprehensive observability and testing patterns that enable debugging and maintenance without impacting production performance. It establishes zero-overhead instrumentation that remains dormant until explicitly activated for troubleshooting.

This layer implements event-based observability where structured events flow to pluggable handlers for logging, metrics, or analysis. The approach ensures that debugging capabilities are always present but never burden the system unless needed. Testing patterns focus on behavioral verification rather than implementation details, ensuring tests remain stable as code evolves.

Operational principles:
- Zero cost when disabled
- Structured event emission
- Context propagation via contextvars
- Behavioral testing over implementation
- Bounded resource usage

The mental model: Build in comprehensive debugging from the start, but ensure it disappears completely when not needed. Test what the system does, not how it does it.

#### Requirements

All code must support zero-overhead debugging and behavioral testing.

#### Mandatory Patterns

**Required Instrumentation**:
```python
import instrumentation

# MUST have zero overhead when disabled
if not handlers:  # Single check, early return
    return

# MUST use structured events
instrumentation.emit('rule.enter', 'expression')

# MUST use context managers for scope
with instrumentation.parsing_rule('function_def'):
    instrumentation.emit('parse.start', 'parsing function')

# MUST support categories
instrumentation.enable_categories('lex')  # Selective debugging

# REQUIRED: Use contextvars for trace propagation
import contextvars

trace_id = contextvars.ContextVar('trace_id')
parse_depth = contextvars.ContextVar('parse_depth', default=0)

# Context automatically propagates through async calls
with instrumentation.set_context(trace_id='abc123'):
    # All nested operations include trace_id
    await parse_async(source)

# Production MUST use sampling
if PRODUCTION:
    handler = instrumentation.create_sampling_handler(
        0.01,  # 1% sampling required
        instrumentation.create_metrics_handler()[0]
    )
```

**Required Testing Patterns**:
```python
# MUST test behavior, not implementation
def test_parser_handles_empty():
    result = parse("")
    assert result == EmptyAST()

# MUST test boundaries
def test_validates_input():
    with pytest.raises(TypeError, match="Expected str"):
        parse(123)

# MUST NOT test private methods
def test_internal_state():  # FORBIDDEN
    assert parser._cache == {}
```

**Required Async Logging**:
```python
# MUST use QueueHandler for high-volume logging
from logging.handlers import QueueHandler, QueueListener

handler = QueueHandler(queue.Queue())
listener = QueueListener(queue, *handlers)
listener.start()  # Non-blocking

# MUST clean up
import atexit
atexit.register(listener.stop)
```

### Forbidden Patterns

```python
# NEVER log in tight loops without guards
for item in million_items:
    log.debug(f"Processing {item}")  # FORBIDDEN

# NEVER use synchronous logging in performance paths
handler = FileHandler('app.log')  # Use QueueHandler instead

# NEVER format eagerly
log.debug(f"Result: {expensive_compute()}")  # FORBIDDEN
log.debug("Result: %s", expensive_compute)   # Use lazy %
```

## Environment & Tooling

> Fill in as necessary

## Further Reading

> Fill in as necessary