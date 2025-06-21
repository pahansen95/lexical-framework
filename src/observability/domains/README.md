# Observability Domains

Observability domains provide specialized APIs that translate domain-specific concepts into structured events. Each domain represents a distinct observability concern - logging, tracing, or metrics - implemented as a thin layer over the core event system.

## Architecture

Domains are organized as a namespace package, meaning this directory contains no shared code or dependencies. Each domain module is completely self-contained and imports only from the parent package's core systems. This isolation ensures:

- No inter-domain dependencies
- Independent evolution of domains
- Clear separation of concerns
- Predictable performance characteristics

## Domain Characteristics

All domains follow a consistent implementation pattern:

- **Event Schema**: Pre-computed event type constants for zero runtime overhead
- **Context Integration**: Automatic propagation via contextvars
- **Zero-Cost Design**: No work performed when no handlers attached
- **Type Safety**: Full type hints on public APIs
- **Domain Handlers**: Specialized handlers that understand domain semantics

## Available Domains

### Logging (`logging.py`)
Hierarchical loggers with severity-based filtering. Provides familiar log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) with automatic parent-child configuration inheritance.

### Tracing (`tracing.py`)
Distributed execution flow tracking through spans. Captures parent-child relationships between operations with automatic duration measurement and error tracking.

### Metrics (`metrics.py`)
Statistical aggregation of numeric measurements. Offers Counter, Gauge, and Histogram types with dimensional data support through labels.

## Creating New Domains

New domains should follow the established development process:

1. **Define Event Schema** - Use constants for all event types
2. **Design Context Variables** - Leverage contextvars for ambient state
3. **Build Domain API** - Create intuitive interfaces that emit events
4. **Implement Domain Handler** - Process domain events appropriately
5. **Ensure Zero Overhead** - Check handlers before any work

Example structure:
```python
# Event types as constants
DOMAIN_PREFIX: Final[str] = "mydomain"
EVENT_ACTION: Final[str] = f"{DOMAIN_PREFIX}.action"

# Domain API
class MyDomain:
    __slots__ = ('config',)
    
    def operation(self, value: Any) -> None:
        if not has_handlers():
            return
        emit(EVENT_ACTION, value)
```

## Performance Expectations

Domains maintain the core system's performance characteristics:

- **Disabled**: Single boolean check (~1ns)
- **Enabled**: Event emission overhead (~100ns)
- **Memory**: Minimal with __slots__ usage
- **Scaling**: O(1) for all operations

The separation between domains and handlers allows flexible aggregation strategies without impacting emission performance.

## Integration Pattern

Domains integrate through the standard observability pipeline:

```python
from observability import attach
from observability.domains import logging, tracing, metrics

# Create domain instances
logger = logging.get_logger('myapp')
counter = metrics.Counter('requests')

# Attach handlers
attach(logging.create_log_formatter())
attach(metrics.create_metrics_aggregator())

# Use domains
with tracing.span('operation'):
    logger.info('Processing request')
    counter.increment()
```

Each domain emits events through the same core system, enabling unified processing while maintaining domain-specific semantics.