"""
Event-Based Instrumentation Framework

A lightweight, zero-overhead instrumentation system for debugging and metrics collection
in language processing tools. The framework provides structured event emission with
pluggable handlers for logging, metrics aggregation, and trace analysis.

## Architecture

The instrumentation system implements a publish-subscribe pattern where the core parsing
logic emits events that are consumed by attached handlers. This separation ensures that
instrumentation logic never interferes with the primary parsing operations.

Key Components:
- Event emission API with automatic context enrichment
- Handler management for flexible event consumption
- Context propagation via Python's contextvars
- Category-based filtering for targeted debugging

## Mental Models

### Event Stream as Narrative

Events form a chronological narrative of the parsing process. Each event captures a
discrete action (token recognition, rule entry/exit, backtracking) with relevant context.
This narrative enables post-hoc debugging and performance analysis without requiring
upfront decisions about what data to collect.

### Zero-Cost Abstraction

When no handlers are attached, the instrumentation has near-zero overhead - just a
single list check and early return. This ensures that production deployments pay no
performance penalty for unused debugging capabilities. The pattern follows:

    if not handlers:
        return  # No work performed

### Context as Ambient State

Parse context (depth, current rule, trace ID) propagates automatically through the
call stack using Python's contextvars. This eliminates parameter threading while
maintaining clear relationships between events. Context enrichment happens at
emission time, not collection time.

### Handlers as Observers

Handlers implement specific observability concerns without knowledge of each other:
- Print handler: Human-readable debugging output
- Metrics handler: Statistical aggregation
- Ring buffer: Recent event history for post-mortem analysis
- File handler: Persistent trace logs

Each handler receives the full event stream and decides independently what to process.

## Design Principles

**Minimal Interface**: The core API consists of just `emit()`, `attach()`, and `detach()`.
Complex functionality emerges from handler composition rather than core complexity.

**Fail-Safe Operation**: Handler errors are isolated and logged but never propagate to
the caller. Instrumentation must never cause parser failures.

**Structured Events**: Events use consistent dot-notation types (e.g., 'rule.enter',
'token.match') with a primary value and optional context dictionary. This enables
both human readability and machine processing.

**Performance by Default**: String formatting uses % notation, handlers are called
without locks held, and filtering happens before event construction. These micro-
optimizations ensure instrumentation remains lightweight even when enabled.

## Usage Patterns

### Basic Instrumentation

    import instrumentation

    # Attach handler for debugging
    instrumentation.attach(instrumentation.create_print_handler())

    # Emit events during parsing
    instrumentation.emit('token.recognize', 'IDENTIFIER', value='foo')
    instrumentation.emit('rule.enter', 'expression')

### Context Management

    # Set parsing context that enriches all nested events
    with instrumentation.parsing_rule('function_def'):
        with instrumentation.increment_depth():
            # Events here include rule='function_def', depth=1
            instrumentation.emit('parse.start', 'parsing function')

### Selective Debugging

    # Enable only lexer events for targeted debugging
    instrumentation.enable_categories('lex')

    # Or disable noisy categories
    instrumentation.disable_categories('token')

### Performance Analysis

    # Time critical operations
    with instrumentation.timed('parse.duration'):
        tree = parser.parse(source)

    # Collect metrics
    handler, get_metrics = instrumentation.create_metrics_handler()
    instrumentation.attach(handler)
    # ... perform parsing ...
    stats = get_metrics()  # Returns counts, durations, etc.

## Integration Guidelines

The instrumentation framework integrates naturally with recursive descent parsers
and lexical analyzers. Recommended instrumentation points:

- Lexer: Token recognition, state transitions, position updates
- Parser: Rule entry/exit, token consumption, backtracking
- Tree building: Node creation, child attachment, position calculation

For production use, instrumentation remains dormant until explicitly enabled,
ensuring zero impact on parsing performance while maintaining the capability for
deep debugging when issues arise.
"""

# Core API
from .core import (
  emit,
  attach,
  detach,
  clear,
  get_handler_count,
  timed,
  traced,
  # Category filtering
  enable_categories,
  disable_categories,
  reset_filters,
  # Context management
  set_context,
  increment_depth,
  parsing_rule,
  # Context variables (for direct access if needed)
  trace_id,
  parse_depth,
  current_rule,
  current_file,
)

# Pre-built handlers (optional)
from .handlers import (
  create_print_handler,
  create_metrics_handler,
  create_ring_buffer,
  create_file_handler,
  create_conditional_handler,
  create_sampling_handler,
)

__all__ = [
  # Core
  "emit",
  "attach",
  "detach",
  "clear",
  "get_handler_count",
  "timed",
  "traced",
  # Configuration
  "enable_categories",
  "disable_categories",
  "reset_filters",
  # Context management
  "set_context",
  "increment_depth",
  "parsing_rule",
  "trace_id",
  "parse_depth",
  "current_rule",
  "current_file",
  # Handlers
  "create_print_handler",
  "create_metrics_handler",
  "create_ring_buffer",
  "create_file_handler",
  "create_conditional_handler",
  "create_sampling_handler",
]
