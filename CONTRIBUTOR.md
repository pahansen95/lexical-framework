# Contributor's Guide

> This document describes expectations of developers, provides development frameworks, establishes directives on coding conventions, offers opinionated recommendations on developer environments, and concludes with further reading for contributor success.

## What is Good Code?

> *"Simplicity is prerequisite for reliability." — Edsger W. Dijkstra*

Every healthy codebase shares a small set of enduring qualities.  This guide opens with them so that every contributor—from first‑time committer to long‑term maintainer—starts with the same mental model and vocabulary.

### 1 — Correctness is non‑negotiable

Our first duty is to ship behaviour that faithfully matches user‑visible intent and internal contracts. Tests, static checks and—where stakes demand—formal proofs are the guard‑rails.  If the behaviour is wrong, nothing else buys redemption.

### 2 — Simplicity beats cleverness

We seek the *least* complicated design that solves today's need while leaving tomorrow unobstructed. Simplicity means code that is easy to reason about—where explicit dependencies and clear data flow trump convenient access patterns. Prefer clear data structures and straight‑line logic to intricate abstractions; embrace YAGNI and delete dead paths early. A function with five parameters that clearly states its needs is simpler than one with zero parameters that reads from hidden global state.

### 3 — Readability enables change

Code is a long‑lived conversation between authors. Names should reveal intent; control flow should read top‑to‑bottom; modules should have single, obvious responsibilities. If an unfamiliar engineer cannot reason about a unit in minutes, refactor or document until they can.

### 4 — Fitness for purpose

Quality lives in context: throughput matters in services, determinism in analytics, robustness in safety‑critical paths. Meet the non‑functional constraints that matter—and prove it with measurements, not intuition.

### 5 — Sustainable maintainability

Every PR must make the future easier, never harder. We budget time for refactoring, guard against technical debt, and keep build, test and deploy feedback loops fast. Code that cannot be tested in isolation will not be maintained in isolation—design decisions must enable unit testing without environmental setup, global state manipulation, or complex mocking. A patch that adds value today at the cost of tomorrow's velocity is not "done".

---

### How to apply this model in practice

| When you…            | Ask yourself…                                                |
| -------------------- | ------------------------------------------------------------ |
| Design a feature     | *Is the simplest correct design obvious?  What will it look like after three more iterations?* |
| Review code          | *Does this change shrink or grow complexity?  Could I maintain it six months from now?* |
| Optimise performance | *Are we optimising the 3 % of code that matters?  Can we isolate the tricky bits behind a clear façade?* |
| Take a shortcut      | *What debt are we incurring?  When—and how—will we pay it off?* |

**Key expectation:**  *If a contribution erodes any pillar above, it requires a clear, written justification and a plan to restore balance.*

Embodying these principles keeps the codebase pliable, reliable and a pleasure to work with—today and for the next generation of contributors.

---

## Writing Good Code

> *"Process without principles is bureaucracy; principles without process is wishful thinking." — Mark Schwartz*

To write "good" code all you need to do is:

1. Think First
2. Code Second
3. Continuously Iterate

We establish a simple framework, The **A · I · O loop**, to guide developers: 

* **Articulate** *what* we're doing and *why* before writing any code.
* **Implement** your vision as models, source code & tests in equal measure.
* **Observe** runtime behavior to understand the gap & iterate accordingly.

Spend roughly equal time articulating & implementing. Automate Observations to quickly iterate.

---

### **A · I · O Loop Procedures**

#### Articulate — *think first*

1. **Discover** – Capture intent; describe your mental models plainly; record user's desired outcomes & expectations of behavior.
2. **Constrain** – Establish (or re-use) a common vernacular; define the extents of your problem space; state your predicates & baseline assumptions.
3. **Architect** – Identify the structure of data & procedural flow of behaviors; understand pre-established patterns and paradigms; posit questions on known unknowns.

Use this process to explore your understanding of the problem & how it maps to your development environment. You are formulating mental models. Spend equal time Articulating as you do Implementing. You're done when you feel like you're hitting diminishing returns (e.g. splitting hairs, chasing rabbits, or talking philosophy).

#### Implement — *code second*

4. **Model** – Write structural & behavioral specifications; formally or otherwise.
5. **Code** – Build a solution that matches your mental models.
6. **Test** – Attempt to falsify behaviors & structures of the code.

Use this process to materialize & validate your mental models. Source code is only one piece of the puzzle. Don't get hung up on premature optimizations or perfection; mark anything that "smells", so we know to come back to it later. Focus on mapping your mental models to executable software. Spend equal time Implementing as you do Articulating. You're done when you feel like you're hitting diminishing returns (e.g. refactoring for style, playing golf or bogged in technical debt).

#### Observe — *continuously iterate*

7. **Measure** – Record & analyze logs, metrics & profiles to determine real world behavior.
8. **Analyze** – Conduct Gap Analysis; compare the observed behavior with your recorded intent.
9. **Iterate** – Measure the error & describe next steps.

Use this process to inform what comes next. Favor automation & fast feedback to increase the time you spend articulating & implementing. If the gap is conceptual, loop to *Articulate*; if it's execution, loop to *Implement*. Iterate until you have "good" code. If you feel the process isn't working, then challenge your approach. If accrued technical debt is a burden, then pay it down. If there is no gap, then congratulations, you're done... for now.

## Good *Python* Coding Conventions

Python code must be correct, simple, and performant. These conventions are requirements for all contributions.

Code organization follows five mandatory layers:
- **Data Layer**: Required structures and state patterns
- **Contract Layer**: Mandatory interfaces and error handling
- **Organization Layer**: Required module and package structure
- **Performance Layer**: Required optimization approaches
- **Operations Layer**: Mandatory debugging and maintenance patterns

### Core Requirements

Write code that leverages Python's built-in optimizations. Never introduce complexity without measured benefit. All patterns must demonstrate quantifiable improvement.

**The Boundary Principle**: Boundaries exist at multiple architectural layers:

- **System boundaries**: Where external data enters (API endpoints, file reads)
- **Configuration boundaries**: Where settings are loaded (application startup)
- **Trust boundaries**: Between validated and unvalidated data
- **Framework boundaries**: Where framework code meets application code

Validate and transform at boundaries. Never reach across boundaries for dependencies.

**The State Lifecycle Principle**: All state has explicit creation, ownership, and destruction phases. Module import is not a lifecycle phase. State creation belongs in factories, initialization functions, or constructors—never at import time.

### Data Layer: Required Structures and State

The Data Layer establishes fundamental patterns for data representation and state management in Python programs. It defines how information flows through the system while maintaining correctness and performance guarantees.

This layer operates on the principle that proper data structure selection eliminates entire classes of bugs while enabling optimal performance. Each built-in type provides specific algorithmic guarantees - dict offers O(1) lookups, set provides O(1) membership testing, and deque enables efficient queue operations. State management patterns distinguish between immutable public interfaces that ensure predictable behavior and mutable internal implementations that maximize performance.

Key concepts:
- Algorithmic guarantees of built-in types
- Immutability boundaries
- State ownership patterns
- Memory efficiency through `__slots__`

The mental model: Choose data structures that make incorrect usage impossible. Design state transitions to be explicit and traceable. Use TypedDicts only when dict behavior is specifically required.

#### Requirements

Data structure selection and state management patterns are mandatory.

#### Mandatory Patterns

**Required Data Structures**:
```python
# Hierarchy: dataclass > TypedDict > dict
# Use TypedDict only when dict behavior is required

# MUST match structure to usage pattern
user_lookup = {}        # O(1) lookup by key
active_users = set()    # O(1) membership testing
task_queue = deque()    # O(1) append/popleft

# MUST use built-in structures before custom
from collections import defaultdict, Counter
visit_count = Counter()  # Instead of manual counting

# MUST limit memory with __slots__ for data classes
@dataclass
class Position:
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

# TypedDict for structured dictionary data
# Use when you need dict behavior with type safety
from typing import TypedDict

class UserData(TypedDict):
    """Typed dictionary when dict operations are required"""
    id: int
    name: str
    active: bool
    tags: list[str]

# TypedDict use cases:
# - JSON/API responses that must remain dicts
# - Interfacing with libraries expecting dicts
# - When dict methods (update, pop) are needed
# - NOT for general data structures (use dataclass)

# Example: API response handling
def process_api_response(data: UserData) -> None:
    # Type-safe dict operations
    user_tags = data.get('tags', [])
    data.update({'active': True})  # Still a dict!
```

**Required State Encapsulation**:
```python
# FORBIDDEN: Module-level mutable state
cache = {}  # Global mutable
client = None  # Deferred global

# REQUIRED: Encapsulated lifecycle
class CacheManager:
    """State with explicit lifecycle"""
    def __init__(self, config: CacheConfig):
        self._cache = {}
        self._config = config

# REQUIRED: Factory for deferred initialization
def create_client(config: ClientConfig) -> Client:
    """Explicit creation point"""
    return Client(config)

# ALLOWED: Module constants only
DEFAULT_TIMEOUT = 30  # Immutable
VALID_MODES = frozenset(['read', 'write'])  # Immutable
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

#### Mandatory Patterns

**Required Boundary Validation**:
```python
from typing import Protocol

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

**Required Dependency Patterns**:
```python
# FORBIDDEN: Hidden dependencies
def process_data(data):
    url = os.environ['API_URL']  # Hidden environmental dependency
    return requests.post(url, data)

# REQUIRED: Explicit dependencies
def process_data(data: dict, api_client: ApiClient) -> Result:
    return api_client.post(data)

# REQUIRED: Configuration as parameter
class Service:
    def __init__(self, config: ServiceConfig, deps: Dependencies):
        self.config = config
        self.deps = deps
```

#### Forbidden Patterns

```python
# NEVER enforce types at runtime
if not isinstance(arg, int):  # FORBIDDEN except at boundaries
    raise TypeError

# NEVER use complex generics
T = TypeVar('T', bound=Hashable)
Parser = Callable[[list[Token]], Result[AST[Node[T]]]]  # FORBIDDEN

# NEVER annotate if it adds no value
def _helper(x: Any) -> Any:  # Just omit annotations
```

### Organization Layer: Required Module Structure

The Organization Layer defines how code is structured into modules and packages to maximize clarity and minimize coupling. It establishes patterns for evolving from simple scripts to complex systems while maintaining navigability and clear dependency relationships.

This layer follows the principle of progressive complexity - start with functions in modules, graduate to classes when state management is needed, and create packages only when modules exceed their single responsibility. Clear boundaries between components are enforced through explicit exports and naming conventions. The approach prevents premature abstraction while supporting natural growth.

Organizational principles:
- Single responsibility per module
- Explicit public interfaces via `__all__`
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

# SHOULD convert to package when:
# - Multiple distinct responsibilities emerge
# - Types/exceptions need their own namespace
# - Implementation details need hiding
# - Testing requires finer granularity

auth/
  __init__.py      # Public exports only
  core.py          # Implementation
  types.py         # Type definitions
  _internal.py     # Private (underscore required)
```

#### Forbidden Patterns

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
- Memory layout (`__slots__`, data locality)
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

# 3. MAY use __slots__ or TypedDicts for frequently instantiated classes
class Token:
    __slots__ = ('type', 'value', 'position')  # Saves 37% memory

# Use TypedDict when:
# - Creating/destroying many instances (>10k/sec)
# - Objects are data-only (no methods needed)
# - Measured as instantiation bottleneck
from typing import TypedDict

class TokenDict(TypedDict):
    type: str
    value: str
    position: int
    
# TypedDict benefits:
# - 60% faster instantiation than classes
# - Native dict performance
# - Zero overhead attribute access
    
# 4. MUST use appropriate concurrency
# I/O-bound: asyncio (preferred) or threading required
async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(
            *[fetch(session, url) for url in urls]
        )

# TODO: Concurrency Thread ExecPool Example

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

#### Forbidden Patterns

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

### Operations Layer: Required Observability and Maintenance

The Operations Layer provides comprehensive observability and testing patterns that enable system analysis and maintenance without impacting production performance. It establishes zero-overhead instrumentation that remains dormant until explicitly activated for investigation.

This layer implements event-based observability where structured events flow to pluggable handlers for logging, metrics, or analysis. The approach ensures that observability infrastructure is always present but never burdens the system unless needed. Testing patterns focus on behavioral verification rather than implementation details, ensuring tests remain stable as code evolves.

The `observability` package provides:
- Zero-cost event emission when no handlers are attached
- Structured event data with automatic context enrichment
- Pluggable handlers for different environments (development, testing, production)
- Async-first design for high-throughput scenarios

Operational principles:
- Zero cost when disabled
- Structured event emission
- Context propagation via contextvars
- Behavioral testing over implementation
- Bounded resource usage

The mental model: Build in comprehensive observability from the start, but ensure it disappears completely when not needed. Test what the system does, not how it does it.

#### Requirements

All code must support zero-overhead observability and behavioral testing.

#### Mandatory Patterns

**Required Instrumentation**:
```python
# Standard observability import pattern
from observability import emit, has_handlers

# MUST have zero overhead when disabled
if not has_handlers():  # Single check, early return
    return

# MUST use structured events
emit('parser.rule.enter', rule='expression', line=42)

# Event structure follows patterns:
# - Dotted event types (domain.category.action)
# - Keyword arguments for event data
# - Automatic timestamp and context capture

# REQUIRED: Use contextvars for trace propagation
import contextvars

trace_id = contextvars.ContextVar('trace_id')
request_id = contextvars.ContextVar('request_id')

# Context automatically propagates through async calls
trace_id.set('abc-123')
emit('parse.start', source_length=len(source))

# Production MUST use sampling handlers
from observability.handlers import SamplingHandler, AsyncHandler

if PRODUCTION:
    handler = SamplingHandler(
        wrapped_handler=AsyncHandler(...),
        sample_rate=0.01  # 1% sampling
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
# MUST use async handlers for high-volume events
from observability.handlers import AsyncHandler, QueueHandler
import queue

# Create async pipeline
event_queue = queue.Queue(maxsize=10000)  # Bounded queue
handler = QueueHandler(event_queue)

# Process events asynchronously
async_handler = AsyncHandler(
    wrapped_handler=your_handler,
    queue_size=1000
)

# MUST clean up on shutdown
import atexit
atexit.register(async_handler.shutdown)
```

#### Forbidden Patterns

```python
# NEVER emit events in tight loops without guards
for item in million_items:
    emit('process.item', item=item)  # FORBIDDEN

# NEVER emit synchronously in performance paths
from observability.handlers import FileHandler
handler = FileHandler('events.log')  # Use AsyncHandler instead

# NEVER construct expensive event data eagerly
emit('result.computed', 
     result=expensive_compute())  # FORBIDDEN - always computed

# CORRECT: Guard emission
if has_handlers():
    emit('result.computed', 
         result_summary=len(results))  # Cheap data only
```

## Forbidden Patterns Reference

### Import-Time Execution
```python
# FORBIDDEN: Any I/O at import
import requests
DEFAULT_RESPONSE = requests.get('http://api.example.com/default')

# FORBIDDEN: Environment reading at import
import os
DATABASE_URL = os.environ['DATABASE_URL']
```

### Singleton Enforcement
```python
# FORBIDDEN: Preventing instantiation
class Database:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### Function-Level Imports
```python
# FORBIDDEN: Hiding dependencies
def process():
    import heavy_module  # Hidden dependency
    return heavy_module.compute()
```

## Escape Hatches

When operational requirements conflict with principles, document thoroughly:

```python
# ESCAPE HATCH: Performance-critical cache
# Justification: 10x performance improvement measured in production
# Limitation: Must call reset_cache() between test suites
# Review date: 2024-Q2
_perf_cache = {}

def get_cache():
    """DO NOT USE without understanding implications"""
    return _perf_cache
```

Every escape hatch requires:
- Measured justification
- Documented limitations
- Review timeline
- Warning in docstring

## Project Environment & Tooling

> Fill in as necessary

## Further Reading

> Fill in as necessary