"""
# Shared Context Module

Provides a thread-safe singleton pattern for ambient observability access. The SharedContext
enables convenient access to observability features without explicit parameter passing,
while maintaining the option for isolated contexts where needed.

## Design Rationale

Many applications need observability at module level for infrastructure concerns (caching,
database connections, system health). The SharedContext provides this ambient access while
preserving the ability to create isolated contexts for testing and domain logic.

## Usage Pattern

```python
# Initialize once at application entry
from observability import SharedContext, ObservabilityConfig
from observability.handlers import JsonHandler

config = ObservabilityConfig(handlers=[JsonHandler(sys.stderr)])
SharedContext.setup(config)

# Use throughout application
from observability.domains.logging import Logger
logger = Logger(__name__, SharedContext.get())
```

## Thread Safety

The SharedContext uses thread-safe initialization with proper locking to ensure
safe concurrent access. Automatic cleanup is registered via atexit for graceful
shutdown.
"""

from typing import Optional, Any
import threading
import sys
import atexit

from .core import ObservabilityConfig, ObservabilityContext, create_observability
from .handlers.sink import PrintHandler


class SharedContext:
  """Singleton providing a shared observability context."""

  _ctx: Optional[ObservabilityContext] = None
  _lock: threading.Lock = threading.Lock()
  _cleanup_registered: bool = False

  @classmethod
  def setup(cls, config: Optional[ObservabilityConfig] = None) -> None:
    """Initialize the shared context.

    Args:
        config: Optional configuration. If None, uses default stderr output.

    Raises:
        RuntimeError: If already initialized.
    """
    with cls._lock:
      if cls._ctx is not None:
        raise RuntimeError("Shared context already initialized. Call teardown() before reinitializing.")

      # Use provided config or create default
      if config is None:
        config = ObservabilityConfig(handlers=[PrintHandler(sys.stderr)], sampling_rate=1.0)

      # Create and start context
      cls._ctx = create_observability(config)
      # cls._ctx.start() # TODO: We need to address Handler Lifecycle Management

      # Register cleanup only once
      if not cls._cleanup_registered:
        atexit.register(cls.teardown)
        cls._cleanup_registered = True

  @classmethod
  def get(cls) -> ObservabilityContext:
    """Get the shared context.

    Returns:
        The shared context instance.

    Raises:
        RuntimeError: If not initialized.
    """
    if cls._ctx is None:
      raise RuntimeError("Shared context not initialized. Call SharedContext.setup() first.")
    return cls._ctx

  @classmethod
  def teardown(cls) -> None:
    """Explicitly teardown the shared context."""
    with cls._lock:
      if cls._ctx is not None:
        # cls._ctx.shutdown() # TODO: We need to address Handler Lifecycle Management
        cls._ctx = None

  @classmethod
  def emit(cls, event_type: str, value: Any, **metadata) -> None:
    """Emit event using the shared context.

    Convenience method that delegates to the context.
    """
    cls.get().emit(event_type, value, **metadata)


__all__ = [
  "SharedContext",
]
