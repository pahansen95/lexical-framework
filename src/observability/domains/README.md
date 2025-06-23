# Observability Domains

Specialized event producers that translate domain-specific operations into structured events
for the observability pipeline. Each domain provides an intuitive API for its particular
concern while maintaining consistent event emission patterns.

## Event Producer Architecture

Domains implement a translation layer between application concepts and system events:

```
Application Concept    Domain Translation    Universal Event
─────────────────     ─────────────────    ───────────────
logger.error()     →  Severity mapping  →  {type: "log.40"}
span.start()       →  Context capture   →  {type: "span.start"}  
counter.increment() →  Label validation →  {type: "metric.counter"}
```

This separation enables domains to:
- Provide natural APIs matching developer expectations
- Enforce domain-specific validation and constraints
- Translate high-level operations into consistent events
- Maintain zero overhead when no handlers are attached

## Domain Characteristics

All domains follow consistent implementation patterns:

**Event Schema**: Pre-computed type constants eliminate runtime string construction
```python
LOG_ERROR: Final[str] = "log.40"     # Computed once at module load
SPAN_START: Final[str] = "span.start" # Zero runtime overhead
```

**Context Integration**: Automatic enrichment via contextvars
```python
from observability import trace_id, request_id
trace_id.get()     # Ambient correlation data
request_id.get()   # Flows through all events
```

**Zero-Cost Design**: Early exits when no consumers exist
```python
if not self._context.has_handlers():
    return  # No work performed
```

**Type Safety**: Full annotations for static analysis
```python
def log(self, level: int, msg: str, **kwargs: Any) -> None:
```

## Available Domains

### Logging
Hierarchical loggers with severity-based filtering. Transforms traditional log calls
into structured events with automatic context enrichment.

### Tracing  
Distributed execution flow tracking through spans. Captures parent-child relationships
and durations as discrete start/end events.

### Metrics
Statistical aggregation of numeric measurements. Provides Counter, Gauge, and Histogram
types that emit measurement events.

## Creating New Domains

New domains should follow the established development process:

### 1. Define Event Schema
Use constants for all event types to ensure zero runtime overhead:
```python
DOMAIN_PREFIX: Final[str] = "mydomain"
EVENT_ACTION: Final[str] = f"{DOMAIN_PREFIX}.action"
```

### 2. Design Context Variables
Leverage contextvars for ambient state that should flow through events:
```python
operation_context: ContextVar[str] = ContextVar('operation_context')
```

### 3. Build Domain API
Create intuitive interfaces that emit events:
```python
class MyDomain:
    def __init__(self, context: ObservabilityContext):
        self._context = context
        
    def operation(self, value: Any) -> None:
        if not self._context.has_handlers():
            return  # Zero-cost when disabled
        self._context.emit(EVENT_ACTION, value)
```

### 4. Implement Domain Handler
Process domain events appropriately:
```python
def create_domain_handler() -> EventHandler:
    def handler(event: EventDict) -> None:
        if event['type'].startswith(DOMAIN_PREFIX):
            # Domain-specific processing
    return handler
```

### 5. Ensure Zero Overhead
Check handlers before any work:
```python
if not self._context.has_handlers():
    return  # Early exit before any computation
```

## Performance Expectations

Domains maintain the core system's performance characteristics:

| Operation | Disabled | Enabled |
|-----------|----------|---------|
| API call | <1ns | Domain-specific |
| Event emission | 0ns | ~100ns |
| Context lookup | 0ns | ~20ns |
| Memory allocation | None | Minimal |

## Integration Pattern

Domains integrate through the standard observability pipeline:

```python
from observability import ObservabilityContext, ObservabilityConfig
from observability.domains.logging import Logger
from observability.domains.tracing import Span
from observability.domains.metrics import Counter

# Create context with handlers
config = ObservabilityConfig(handlers=[...])
context = ObservabilityContext(config)
context.start()

# Create domain instances
logger = Logger('myapp', context)
counter = Counter('requests', context)

# Use domains - events flow to all attached handlers
with Span('operation', context) as span:
    logger.info('Processing request')
    counter.increment()
```

Each domain emits events through the same core system, enabling unified processing
while maintaining domain-specific semantics. This architecture allows teams to start
with one domain and incrementally add others without architectural changes.