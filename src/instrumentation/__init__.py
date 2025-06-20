"""
Event-based instrumentation for debugging and metrics collection.

Architecture:
- core: Minimal event emission and handler management
- handlers: Pre-built handlers for common use cases

Usage:
    import instrumentation

    # Attach a handler
    instrumentation.attach(instrumentation.create_print_handler())

    # Emit events
    instrumentation.emit('parse.start', 'file.py')
"""

# Core API
from .core import emit, attach, detach, clear, get_handler_count, timed, traced

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
  # Handlers
  "create_print_handler",
  "create_metrics_handler",
  "create_ring_buffer",
  "create_file_handler",
  "create_conditional_handler",
  "create_sampling_handler",
]
