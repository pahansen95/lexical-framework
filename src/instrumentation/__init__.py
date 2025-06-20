"""
Event-based instrumentation for debugging and metrics collection.

Architecture:
- core: Minimal event emission and handler management
- handlers: Pre-built handlers for common use cases

Usage:
    import instrumentation

    # Configure behavior
    instrumentation.enable_categories('lex', 'parse')

    # Attach a handler
    instrumentation.attach(instrumentation.create_print_handler())

    # Emit events with automatic context
    with instrumentation.parsing_rule('expression'):
        instrumentation.emit('parse.start', 'file.py')
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
