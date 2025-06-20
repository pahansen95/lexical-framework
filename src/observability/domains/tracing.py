"""
Tracing domain for distributed execution flow tracking.

The tracing domain captures the causal relationships between operations through
spans - timed segments of execution that form a directed acyclic graph. Each span
represents a logical unit of work with clear start/end boundaries, automatic duration
measurement, and optional metadata describing the operation.

Mental Model:
A trace tells the story of an operation's journey through the system. Like chapters
in a book, spans represent discrete sections of work that combine to form the complete
narrative. Parent spans contain child spans, creating a hierarchy that mirrors the
actual call stack or logical flow of the application.

Key Concepts:
- Span: A timed operation with metadata, representing a unit of work
- Trace: A collection of related spans sharing a common trace_id
- Parent-Child Relationship: Spans nest to show operation hierarchy
- Context Propagation: Trace context flows automatically through execution

Design Principles:
- Zero-overhead when tracing disabled
- Automatic parent-child relationships via context
- Rich metadata without performance penalty
- Natural integration with async/sync code

The implementation leverages contextvars for ambient span tracking, ensuring that
child spans automatically discover their parent without explicit parameter passing.
This creates an intuitive API where the code structure naturally produces the
correct trace structure.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Final, Iterator, Optional
import time
import weakref

from ..core import emit, has_handlers

# Event schema
SPAN_PREFIX: Final[str] = "span"
SPAN_START: Final[str] = f"{SPAN_PREFIX}.start"
SPAN_END: Final[str] = f"{SPAN_PREFIX}.end"

# Context variables
current_span: Final[ContextVar[Optional['Span']]] = ContextVar('current_span', default=None)

# Span ID generation (simple counter for performance)
_span_counter: int = 0
_counter_lock = __import__('threading').Lock()

def _generate_span_id() -> str:
    """Generate unique span ID efficiently."""
    global _span_counter
    with _counter_lock:
        _span_counter += 1
        return f"{_span_counter:x}"  # Hex for compactness


class Span:
    """
    Represents a single operation in a trace.
    
    Spans track the lifecycle of an operation from start to end,
    measuring duration and capturing success/failure status.
    """
    
    __slots__ = ('span_id', 'operation', 'parent_id', 'start_ns', 
                 '_end_ns', 'attributes', '_parent_ref')
    
    def __init__(self, operation: str, **attributes: Any):
        """
        Initialize a span.
        
        Args:
            operation: Name describing the operation
            **attributes: Additional span metadata
        """
        self.span_id = _generate_span_id()
        self.operation = operation
        self.start_ns = time.perf_counter_ns()
        self._end_ns: Optional[int] = None
        self.attributes = attributes
        
        # Establish parent relationship
        parent = current_span.get()
        if parent:
            self.parent_id = parent.span_id
            self._parent_ref = weakref.ref(parent)
        else:
            self.parent_id = None
            self._parent_ref = None
    
    @property
    def duration_ns(self) -> Optional[int]:
        """Duration in nanoseconds if span has ended."""
        if self._end_ns is None:
            return None
        return self._end_ns - self.start_ns
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Add or update span attribute."""
        self.attributes[key] = value
    
    def end(self, error: Optional[str] = None) -> None:
        """
        End the span and emit completion event.
        
        Args:
            error: Error message if operation failed
        """
        if self._end_ns is not None:
            return  # Already ended
        
        self._end_ns = time.perf_counter_ns()
        duration_ns = self._end_ns - self.start_ns
        
        emit(SPAN_END,
             self.operation,
             span_id=self.span_id,
             parent_id=self.parent_id,
             duration_ns=duration_ns,
             success=error is None,
             error=error,
             **self.attributes)


@contextmanager
def span(operation: str, **attributes: Any) -> Iterator[Span]:
    """
    Create a span for the duration of a block.
    
    The span automatically tracks parent-child relationships and
    measures execution time. Errors are captured and included in
    the span data.
    
    Args:
        operation: Name describing the operation
        **attributes: Additional span metadata
        
    Yields:
        The created Span instance
        
    Example:
        with span('database.query', table='users') as s:
            s.set_attribute('query_type', 'SELECT')
            result = db.execute(query)
    """
    # Zero-overhead when disabled
    if not has_handlers():
        # Return dummy span that does nothing
        dummy = Span.__new__(Span)
        dummy.span_id = ''
        dummy.operation = operation
        dummy.attributes = {}
        dummy.set_attribute = lambda k, v: None
        dummy.end = lambda error=None: None
        yield dummy
        return
    
    # Create and start span
    s = Span(operation, **attributes)
    emit(SPAN_START,
         operation,
         span_id=s.span_id,
         parent_id=s.parent_id,
         **attributes)
    
    # Set as current span
    token = current_span.set(s)
    try:
        yield s
        s.end()
    except Exception as e:
        s.end(error=str(e))
        raise
    finally:
        current_span.reset(token)


def create_trace_handler(
    include_timing: bool = True,
    max_depth: int = 50
) -> Any:
    """
    Create a handler that formats trace events for debugging.
    
    Args:
        include_timing: Include duration in output
        max_depth: Maximum nesting depth to display
        
    Returns:
        Event handler for trace visualization
    """
    # Track active spans for correlation
    active_spans: Dict[str, Dict[str, Any]] = {}
    
    def trace_handler(event: Dict[str, Any]) -> None:
        if not event['type'].startswith(SPAN_PREFIX):
            return
        
        event_type = event['type']
        span_id = event.get('span_id', '')
        
        if event_type == SPAN_START:
            # Store span info for correlation
            active_spans[span_id] = {
                'operation': event['value'],
                'parent_id': event.get('parent_id'),
                'depth': 0,
                'attributes': {k: v for k, v in event.items() 
                             if k not in ['type', 'value', 'span_id', 'parent_id', 'timestamp_ns']}
            }
            
            # Calculate depth
            parent_id = event.get('parent_id')
            if parent_id and parent_id in active_spans:
                parent_depth = active_spans[parent_id]['depth']
                active_spans[span_id]['depth'] = parent_depth + 1
            
            depth = active_spans[span_id]['depth']
            if depth > max_depth:
                return
            
            indent = '  ' * depth
            attrs = active_spans[span_id]['attributes']
            attr_str = ' '.join(f'{k}={v}' for k, v in attrs.items()) if attrs else ''
            
            print(f"{indent}→ {event['value']} [{span_id}] {attr_str}")
        
        elif event_type == SPAN_END:
            if span_id not in active_spans:
                return
            
            span_info = active_spans.pop(span_id)
            depth = span_info['depth']
            if depth > max_depth:
                return
            
            indent = '  ' * depth
            operation = span_info['operation']
            
            # Format output
            if include_timing:
                duration_ns = event.get('duration_ns', 0)
                duration_ms = duration_ns / 1_000_000
                timing = f" ({duration_ms:.2f}ms)"
            else:
                timing = ""
            
            success = event.get('success', True)
            status = '✓' if success else '✗'
            error = f" error={event['error']}" if not success else ""
            
            print(f"{indent}← {operation} [{span_id}] {status}{timing}{error}")
    
    trace_handler.__name__ = f"trace_handler(timing={include_timing})"
    return trace_handler


# Utility functions
def get_current_span() -> Optional[Span]:
    """Get the currently active span."""
    return current_span.get()


def link_to_parent(parent_span_id: str) -> None:
    """
    Manually set parent span ID for cross-process tracing.
    
    Args:
        parent_span_id: Parent span ID from another process
    """
    current = current_span.get()
    if current and current.parent_id is None:
        current.parent_id = parent_span_id


# Public exports
__all__ = [
    # Main API
    'span',
    'Span',
    
    # Utilities
    'get_current_span',
    'link_to_parent',
    
    # Handlers
    'create_trace_handler',
]