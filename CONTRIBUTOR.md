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

**Public API Typing**:

```python
from typing import Optional, List, Iterator

def tokenize(text: str) -> List[Token]:
    """Full type information for public interfaces."""
    return list(_generate_tokens(text))

def _generate_tokens(text: str) -> Iterator[Token]:
    # Internal functions can omit types if obvious
    position = 0
    while position < len(text):
        yield _next_token(text, position)
```

**Protocol Definitions**:

```python
from typing import Protocol

class Parseable(Protocol):
    """Define expected interfaces without inheritance."""
    def parse(self) -> Any: ...
```

### Performance Patterns

Write standard patterns that Python can optimize. Use generators for memory efficiency. Profile before optimizing.

**Generator-Based Processing**:

```python
def process_large_dataset(path: Path) -> Iterator[Result]:
    """Memory-efficient streaming processing."""
    with open(path) as file:
        for line in file:
            if data := parse_line(line):
                yield process_record(data)
```

**Built-in Optimization**:

```python
# Prefer built-in operations
text = ''.join(parts)                    # Not: text = '' + part1 + part2
counts = Counter(items)                  # Not: manual counting loop
filtered = [x for x in items if valid(x)]  # Not: manual append loop
```

### Code Organization

Structure code to minimize complexity. Prefer modules and functions over classes. Keep inheritance shallow.

**When to Use Classes**:

Classes are appropriate when you need:

1. **Stateful objects** - Managing mutable state across method calls
2. **Resource management** - Implementing context managers for cleanup
3. **Polymorphism** - Multiple implementations of the same interface
4. **Data encapsulation** - Bundling related data with behavior

```python
# Good use of class - stateful parser
class Parser:
    """Maintains parsing state across multiple operations."""
    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._position = 0
    
    def parse(self) -> AST:
        # Multiple methods operate on shared state
        return self._parse_program()

# Good use of class - resource management
class DatabaseConnection:
    """Manages connection lifecycle."""
    def __enter__(self):
        self._conn = connect()
        return self._conn
    
    def __exit__(self, *args):
        self._conn.close()
```

**When to Use Modules + Functions**:

Prefer module-level functions when:

1. **Stateless operations** - Pure transformations
2. **Single responsibility** - One clear purpose
3. **Reusable utilities** - Shared across modules
4. **Simple workflows** - Linear processing

```python
# tokenizer.py - Stateless operations as functions
def tokenize(text: str) -> List[Token]:
    """Transform text to tokens - no state needed."""
    return list(_generate_tokens(text))

def _generate_tokens(text: str) -> Iterator[Token]:
    """Internal generator for memory efficiency."""
    position = 0
    while position < len(text):
        token = _match_token(text, position)
        yield token
        position += token.length

# utils.py - Reusable utilities
def normalize_path(path: str) -> Path:
    """Pure function - same input always gives same output."""
    return Path(path).resolve()
```

**Module Structure Pattern**:

```python
# feature.py - Organize by domain capability

# Public API functions at top
def process_data(input_path: Path) -> Result:
    """Main entry point for data processing."""
    data = load_data(input_path)
    validated = validate_data(data)
    return transform_data(validated)

def validate_data(data: RawData) -> ValidData:
    """Secondary public function."""
    # Implementation

# Internal helpers prefixed with underscore
def _parse_record(line: str) -> Record:
    """Internal parsing logic."""
    # Implementation

# Constants and configuration
DEFAULT_ENCODING = 'utf-8'
SUPPORTED_FORMATS = {'json', 'csv', 'tsv'}
```

### Observability

Build in lightweight debugging and monitoring from the start. Use lazy evaluation to minimize overhead.

**Structured Logging Pattern**:

```python
import logging
import contextvars
from typing import Any, Dict

# Thread-local context for correlation
request_id: contextvars.ContextVar[str] = contextvars.ContextVar('request_id')

class StructuredLogger:
    """Add structured context to all log messages."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._base_context = {'component': name}
    
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Merge base context, request context, and extra fields."""
        context = self._base_context.copy()
        
        # Add correlation ID if present
        if rid := request_id.get(None):
            context['request_id'] = rid
        
        context.update(extra)
        return {'extra': context}
    
    def info(self, msg: str, **kwargs):
        self.logger.info(msg, **self._add_context(kwargs))

# Usage
logger = StructuredLogger(__name__)

def process_request(request):
    # Set correlation ID for this request
    request_id.set(request.id)
    
    logger.info("Processing request", 
                user_id=request.user_id,
                path=request.path)
```

**Metrics Collection Pattern**:

```python
from collections import defaultdict
from contextlib import contextmanager
from time import perf_counter
import atexit

class Metrics:
    """Thread-safe metrics collection with zero allocation overhead."""
    
    # Use module-level storage for efficiency
    _counters = defaultdict(int)
    _timers = defaultdict(lambda: {'count': 0, 'total': 0.0})
    
    @classmethod
    def inc(cls, name: str, value: int = 1) -> None:
        """Increment counter - minimal overhead."""
        cls._counters[name] += value
    
    @classmethod
    @contextmanager
    def timer(cls, name: str):
        """Time operation with context manager."""
        start = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - start
            stats = cls._timers[name]
            stats['count'] += 1
            stats['total'] += elapsed
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get all metrics for reporting."""
        return {
            'counters': dict(cls._counters),
            'timers': {
                name: {
                    'count': stats['count'],
                    'total': stats['total'],
                    'average': stats['total'] / stats['count'] if stats['count'] else 0
                }
                for name, stats in cls._timers.items()
            }
        }

# Register cleanup
atexit.register(lambda: logger.info("Final metrics", **Metrics.get_stats()))

# Usage
def handle_request(request):
    Metrics.inc('requests_received')
    
    with Metrics.timer('request_processing'):
        result = process(request)
    
    Metrics.inc('requests_completed')
    return result
```

**Debug Tracing Pattern**:

```python
from contextlib import contextmanager
from functools import wraps

# Development-only tracing
if __debug__:
    _trace_stack = []
    
    @contextmanager
    def trace(operation: str, **context):
        """Trace execution in debug mode only."""
        entry = {'op': operation, 'context': context, 'start': perf_counter()}
        _trace_stack.append(entry)
        
        try:
            yield
        except Exception as e:
            # Log error with full context
            logger.error("Error in %s: %s", operation, e,
                        stack=[t['op'] for t in _trace_stack])
            raise
        finally:
            entry['duration'] = perf_counter() - entry['start']
            _trace_stack.pop()
            
            # Log slow operations
            if entry['duration'] > 0.1:
                logger.warning("Slow operation: %s took %.2fs",
                             operation, entry['duration'])
else:
    # No-op in production
    @contextmanager
    def trace(operation: str, **context):
        yield

# Usage - compiles out in production
def parse_expression(tokens):
    with trace('parse_expression', token_count=len(tokens)):
        return _parse_expr_impl(tokens)
```

**Production Sampling Pattern**:

```python
import random
from functools import wraps

def sample_trace(rate: float = 0.01):
    """Decorator for sampled tracing in production."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Sample at specified rate
            should_trace = random.random() < rate
            
            if should_trace:
                with Metrics.timer(f'{func.__module__}.{func.__name__}'):
                    logger.debug("Executing %s", func.__name__)
                    result = func(*args, **kwargs)
                    logger.debug("Completed %s", func.__name__)
                    return result
            else:
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Usage - 1% sampling in production
@sample_trace(rate=0.01)
def expensive_operation(data):
    return process_data(data)
```

**Error Context Pattern**:

```python
class ContextualError(Exception):
    """Exception that carries debugging context."""
    
    def __init__(self, message: str, **context):
        super().__init__(message)
        self.context = context
    
    def __str__(self):
        context_str = ', '.join(f"{k}={v}" for k, v in self.context.items())
        return f"{super().__str__()} [{context_str}]"

# Usage
def parse_token(token, position):
    if token.type == 'INVALID':
        raise ContextualError(
            "Invalid token",
            token_type=token.type,
            position=position,
            line=token.line,
            column=token.column
        )
```

**Observability Implementation Checklist**:

1. **Always use structured logging** - Include correlation IDs and context
2. **Implement metrics from the start** - Count operations and time critical paths
3. **Use conditional compilation** - `__debug__` for development-only overhead
4. **Sample in production** - Trace a percentage of operations to control overhead
5. **Capture error context** - Include relevant state in exceptions
6. **Export metrics on shutdown** - Use atexit handlers for final reporting
7. **Keep overhead minimal** - Lazy formatting, conditional evaluation

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

