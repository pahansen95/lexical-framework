"""
# Observability Package

A unified event emission infrastructure that provides zero-overhead instrumentation
for logging, tracing, and metrics collection. The package implements a context-based
architecture where all observability state is encapsulated in explicit context objects.

## Architecture

The observability system uses explicit contexts to manage state and configuration:

```
Application Code
    ↓
ObservabilityContext ←── SharedContext.get()
    ↓ emit()
Handler Pipeline
    ├─→ Logging Handler → File/Console
    ├─→ Metrics Handler → Aggregation/Export
    └─→ Trace Handler   → Span Collection
```

## Context-Based Design

All observability state lives within context objects, eliminating global state:

```python
# Create configured context
config = ObservabilityConfig(
    handlers=[ManagedFileHandler('app.log'), JsonHandler(sys.stderr)],
    sampling_rate=0.1
)
context = ObservabilityContext(config)
context.start()

# Or use shared context for convenience
SharedContext.setup(config)
context = SharedContext.get()

# Instantiate domains directly
from observability.domains.logging import Logger
from observability.domains.tracing import Span
from observability.domains.metrics import Counter

logger = Logger('myapp', context)
logger.info('Application started')

with Span('operation', context) as span:
    span.set_attribute('user_id', 123)

counter = Counter('requests', context)
counter.increment(endpoint='/api/users')
```

## Zero-Overhead Guarantee

When no handlers are attached, the entire system reduces to a single boolean check,
ensuring production code pays no performance penalty for unused instrumentation.
"""

# Context infrastructure
from .core import (
  ObservabilityContext,
  ObservabilityConfig,
  create_observability,
)

# Shared Context
from .shared import SharedContext

# Handler imports
from .handlers import (
  PrintHandler,
  JsonHandler,
  ManagedFileHandler,
  BufferHandler,
  filtered,
  sampled,
  AsyncHandlerWorker,
  TimeDeltaHandler,
  FanoutHandler,
  FallbackHandler,
)

# Type exports
from .types import EventDict, EventHandler

# Context variables
import contextvars
from typing import Final, Optional

trace_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("trace_id", default=None)
request_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("request_id", default=None)
operation_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar("operation_id", default=None)

# Public API
__all__ = [
  # Context infrastructure
  "ObservabilityContext",
  "ObservabilityConfig",
  "create_observability",
  # Shared Context
  "SharedContext",
  # Handler classes
  "PrintHandler",
  "JsonHandler",
  "ManagedFileHandler",
  "BufferHandler",
  "filtered",
  "sampled",
  "AsyncHandlerWorker",
  "TimeDeltaHandler",
  "FanoutHandler",
  "FallbackHandler",
  # Types
  "EventDict",
  "EventHandler",
  # Context variables
  "trace_id",
  "request_id",
  "operation_id",
]
