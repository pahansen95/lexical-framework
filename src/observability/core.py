"""
Core event emission system with zero-overhead instrumentation.

Provides the foundational event pipeline that all observability domains build upon.
The system achieves near-zero overhead through careful design: a single boolean
check when no handlers are attached, lazy event construction, and lock-free emission.
"""

import contextvars
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Final, Iterator, List, Optional, Set

from .types import EventDict, EventHandler, HandlerList, CategorySet

# Module initialization time for relative timestamps
_START_TIME_NS: Final[int] = time.perf_counter_ns()

# Standard context variables for automatic propagation
trace_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar('trace_id', default=None)
request_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar('request_id', default=None)
operation_id: Final[contextvars.ContextVar[Optional[str]]] = contextvars.ContextVar('operation_id', default=None)


class _EventSystemState:
    """
    Encapsulates mutable state for the event system.
    
    Thread-safe state management with minimal locking overhead.
    Category filtering uses cached lookups for performance.
    """
    
    __slots__ = ('handlers', 'lock', 'category_mode', 'categories', '_category_cache')
    
    def __init__(self):
        self.handlers: HandlerList = []
        self.lock = threading.Lock()
        self.category_mode: Optional[str] = None  # None | 'allow' | 'block'
        self.categories: CategorySet = set()
        self._category_cache: Dict[str, str] = {}  # event_type -> category
    
    def get_category(self, event_type: str) -> str:
        """Extract category with caching for performance."""
        if event_type not in self._category_cache:
            self._category_cache[event_type] = event_type.split('.', 1)[0]
        return self._category_cache[event_type]
    
    def reset(self) -> None:
        """Reset all state (primarily for testing)."""
        with self.lock:
            self.handlers.clear()
        self.category_mode = None
        self.categories.clear()
        self._category_cache.clear()


# Global state instance
_state = _EventSystemState()


# Performance utilities
def has_handlers() -> bool:
    """
    Check if any handlers are attached.
    
    Critical performance path - used by domains for early exit.
    Returns immediately without locks.
    """
    return bool(_state.handlers)


def get_handler_count() -> int:
    """Return number of attached handlers."""
    return len(_state.handlers)


# Core emission
def emit(event_type: str, value: Any, **metadata: Any) -> None:
    """
    Emit an event through the observability pipeline.
    
    Zero overhead when no handlers are attached. Automatically enriches
    events with context from contextvars.
    
    Args:
        event_type: Dot-notation event identifier (e.g., 'log.error')
        value: Primary event value
        **metadata: Additional event metadata
        
    Raises:
        TypeError: If event_type is not a string
        ValueError: If event_type is empty
    """
    # Boundary validation
    if not isinstance(event_type, str):
        raise TypeError(f"event_type must be str, got {type(event_type).__name__}")
    if not event_type:
        raise ValueError("event_type cannot be empty")
    
    # Zero-overhead early exit
    if not _state.handlers:
        return
    
    # Category filtering
    if _state.category_mode:
        category = _state.get_category(event_type)
        if _state.category_mode == 'allow' and category not in _state.categories:
            return
        elif _state.category_mode == 'block' and category in _state.categories:
            return
    
    # Build event
    event: EventDict = {
        'type': event_type,
        'value': value,
        'timestamp_ns': time.perf_counter_ns() - _START_TIME_NS,
    }
    
    # Add context variables if set
    if (tid := trace_id.get()) is not None:
        event['trace_id'] = tid
    if (rid := request_id.get()) is not None:
        event['request_id'] = rid
    if (oid := operation_id.get()) is not None:
        event['operation_id'] = oid
    
    # Add metadata
    event.update(metadata)
    
    # Snapshot handlers to avoid holding lock during dispatch
    with _state.lock:
        handlers = _state.handlers.copy()
    
    # Dispatch with error isolation
    for handler in handlers:
        try:
            handler(event)
        except Exception as e:
            if __debug__:
                # In debug mode, log handler errors
                handler_name = getattr(handler, '__name__', repr(handler))
                print(f"Handler error in {handler_name}: {e}", file=sys.stderr)


# Handler management
def attach(handler: EventHandler) -> None:
    """
    Attach an event handler.
    
    Args:
        handler: Callable accepting EventDict
        
    Raises:
        TypeError: If handler is not callable
    """
    if not callable(handler):
        raise TypeError(f"Handler must be callable, got {type(handler).__name__}")
    
    with _state.lock:
        _state.handlers.append(handler)


def detach(handler: EventHandler) -> None:
    """
    Remove an event handler.
    
    Silently succeeds if handler not attached.
    """
    with _state.lock:
        try:
            _state.handlers.remove(handler)
        except ValueError:
            pass  # Handler not attached


def clear() -> None:
    """Remove all handlers."""
    with _state.lock:
        _state.handlers.clear()


# Category filtering
def enable_categories(*categories: str) -> None:
    """
    Enable only specified event categories.
    
    Events not matching these categories will be filtered.
    
    Args:
        *categories: Category prefixes to allow
        
    Raises:
        TypeError: If any category is not a string
        ValueError: If any category is empty
    """
    for cat in categories:
        if not isinstance(cat, str):
            raise TypeError(f"Category must be str, got {type(cat).__name__}")
        if not cat:
            raise ValueError("Category cannot be empty")
    
    _state.category_mode = 'allow'
    _state.categories.update(categories)


def disable_categories(*categories: str) -> None:
    """
    Disable specified event categories.
    
    Events matching these categories will be filtered.
    
    Args:
        *categories: Category prefixes to block
        
    Raises:
        TypeError: If any category is not a string
        ValueError: If any category is empty
    """
    for cat in categories:
        if not isinstance(cat, str):
            raise TypeError(f"Category must be str, got {type(cat).__name__}")
        if not cat:
            raise ValueError("Category cannot be empty")
    
    _state.category_mode = 'block'
    _state.categories.update(categories)


def reset_filters() -> None:
    """Clear all category filters."""
    _state.category_mode = None
    _state.categories.clear()


# Context management
@contextmanager
def set_context(**kwargs: Any) -> Iterator[None]:
    """
    Temporarily set context variables.
    
    Context automatically propagates to all events emitted within
    the managed block.
    
    Example:
        with set_context(trace_id='abc123', request_id='req-456'):
            emit('operation.start', 'processing')
            # Events include trace_id and request_id
    """
    tokens = []
    context_vars = {
        'trace_id': trace_id,
        'request_id': request_id,
        'operation_id': operation_id,
    }
    
    for name, value in kwargs.items():
        if name in context_vars:
            var = context_vars[name]
            tokens.append(var.set(value))
    
    try:
        yield
    finally:
        for token in tokens:
            token.var.reset(token)


# Testing support
@contextmanager
def capture_events() -> Iterator[List[EventDict]]:
    """
    Capture events for testing.
    
    Provides a list that accumulates all events emitted within
    the context. Useful for verifying domain behavior.
    
    Example:
        with capture_events() as events:
            logger.error('Test message')
        assert events[0]['type'] == 'log.40'
    """
    captured: List[EventDict] = []
    
    def capture_handler(event: EventDict) -> None:
        captured.append(event.copy())
    
    attach(capture_handler)
    try:
        yield captured
    finally:
        detach(capture_handler)


# Export public API
__all__ = [
    # Event emission
    'emit',
    
    # Handler management
    'attach',
    'detach',
    'clear',
    
    # Performance utilities
    'has_handlers',
    'get_handler_count',
    
    # Context management
    'set_context',
    'capture_events',
    
    # Category filtering
    'enable_categories',
    'disable_categories',
    'reset_filters',
    
    # Context variables (for direct access if needed)
    'trace_id',
    'request_id',
    'operation_id',
]