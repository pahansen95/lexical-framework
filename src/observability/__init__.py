"""
Observability package for zero-overhead instrumentation.

Provides unified event emission infrastructure with specialized domains for
logging, tracing, and metrics. Designed for minimal performance impact when
disabled and efficient operation when enabled.

Basic Usage:
    from observability import emit, attach, logging

    # Attach a handler
    attach(create_print_handler())
    
    # Use specialized domains
    logger = logging.get_logger('myapp')
    logger.info('Application started')
    
    with tracing.span('operation'):
        metrics.Counter('requests').increment()

Core Concepts:
    - Events flow through a central pipeline
    - Handlers process events asynchronously
    - Domains provide specialized APIs
    - Zero overhead when no handlers attached
"""

from typing import Any

# Core event system
from .core import (
    # Event emission
    emit,
    # Handler management
    attach,
    detach,
    clear,
    # Performance utilities
    has_handlers,
    get_handler_count,
    # Context management
    set_context,
    # Category filtering
    enable_categories,
    disable_categories,
    reset_filters,
    # Testing support
    capture_events,
)

# Handler utilities
from .handlers import (
    # Basic handlers
    create_print_handler,
    create_file_handler,
    create_buffer_handler,
    # Composition handlers
    create_async_handler,
    create_conditional_handler,
    create_sampling_handler,
)

# Type exports for static analysis
from .types import EventDict, EventHandler


class _DomainNamespace:
    """Lazy-loading namespace for domain modules."""
    
    __slots__ = ('_module_name', '_module', '_loaded_attrs')
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
        self._loaded_attrs = {}
    
    def __getattr__(self, name: str) -> Any:
        # Cache individual attributes to avoid repeated lookups
        if name in self._loaded_attrs:
            return self._loaded_attrs[name]
        
        # Lazy import on first access
        if self._module is None:
            import importlib
            self._module = importlib.import_module(self._module_name)
        
        attr = getattr(self._module, name)
        self._loaded_attrs[name] = attr
        return attr
    
    def __dir__(self):
        # Enable IDE autocompletion
        if self._module is None:
            import importlib
            self._module = importlib.import_module(self._module_name)
        return dir(self._module)


# Domain namespaces
logging = _DomainNamespace('observability.domains.logging')
tracing = _DomainNamespace('observability.domains.tracing')
metrics = _DomainNamespace('observability.domains.metrics')

# Public API
__all__ = [
    # Core functions
    'emit',
    'attach',
    'detach',
    'clear',
    'has_handlers',
    'get_handler_count',
    'set_context',
    'capture_events',
    'enable_categories',
    'disable_categories',
    'reset_filters',
    
    # Handler factories
    'create_print_handler',
    'create_file_handler',
    'create_buffer_handler',
    'create_async_handler',
    'create_conditional_handler',
    'create_sampling_handler',
    
    # Types
    'EventDict',
    'EventHandler',
    
    # Domain namespaces
    'logging',
    'tracing',
    'metrics',
]