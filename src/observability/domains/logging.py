"""
Logging domain for structured message recording.

The logging domain provides hierarchical loggers with severity-based filtering.
Events are emitted only when the severity meets the configured threshold, ensuring
zero overhead for disabled log levels.

Key concepts:
- Logger: Named message emitter with severity threshold
- Severity: Numeric level indicating message importance
- Hierarchy: Child loggers inherit configuration from parents
"""

from typing import Any, Dict, Final, Optional, Tuple
import weakref

from ..core import emit, has_handlers

# Event schema
LOG_PREFIX: Final[str] = "log"

# Severity levels
CRITICAL: Final[int] = 50
ERROR: Final[int] = 40
WARNING: Final[int] = 30
INFO: Final[int] = 20
DEBUG: Final[int] = 10
NOTSET: Final[int] = 0

# Pre-computed event types for performance
LOG_CRITICAL: Final[str] = f"{LOG_PREFIX}.{CRITICAL}"
LOG_ERROR: Final[str] = f"{LOG_PREFIX}.{ERROR}"
LOG_WARNING: Final[str] = f"{LOG_PREFIX}.{WARNING}"
LOG_INFO: Final[str] = f"{LOG_PREFIX}.{INFO}"
LOG_DEBUG: Final[str] = f"{LOG_PREFIX}.{DEBUG}"

# Map severity to event type
_SEVERITY_TO_EVENT: Final[Dict[int, str]] = {
    CRITICAL: LOG_CRITICAL,
    ERROR: LOG_ERROR,
    WARNING: LOG_WARNING,
    INFO: LOG_INFO,
    DEBUG: LOG_DEBUG,
}

# Logger hierarchy storage
_loggers: Dict[str, 'Logger'] = {}
_root_logger: Optional['Logger'] = None


class Logger:
    """
    Hierarchical logger with severity-based filtering.
    
    Loggers form a dot-separated hierarchy where children inherit
    configuration from parents unless explicitly set.
    """
    
    __slots__ = ('name', 'level', '_parent_ref')
    
    def __init__(self, name: str, parent: Optional['Logger'] = None):
        """
        Initialize logger.
        
        Args:
            name: Logger name (dot-separated hierarchy)
            parent: Parent logger for configuration inheritance
        """
        self.name = name
        self.level = NOTSET  # Inherit from parent by default
        self._parent_ref = weakref.ref(parent) if parent else None
    
    @property
    def effective_level(self) -> int:
        """Get effective level considering hierarchy."""
        if self.level != NOTSET:
            return self.level
        
        parent = self._parent_ref() if self._parent_ref else None
        if parent:
            return parent.effective_level
        
        return WARNING  # Default when no parent
    
    def set_level(self, level: int) -> None:
        """
        Set logger severity threshold.
        
        Args:
            level: Minimum severity for message emission
        """
        self.level = level
    
    def is_enabled_for(self, level: int) -> bool:
        """Check if severity level is enabled."""
        if not has_handlers():
            return False
        return level >= self.effective_level
    
    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        Log message at specified severity.
        
        Args:
            level: Message severity
            msg: Message template (% formatting)
            *args: Positional arguments for template
            **kwargs: Extra fields added to event
        """
        if not self.is_enabled_for(level):
            return
        
        # Get pre-computed event type
        event_type = _SEVERITY_TO_EVENT.get(level, f"{LOG_PREFIX}.{level}")
        
        # Format message lazily
        if args:
            try:
                message = msg % args
            except (TypeError, ValueError) as e:
                # Formatting error - log the template and args
                message = f"Log format error: {msg} % {args!r} - {e}"
        else:
            message = msg
        
        # Emit structured event
        emit(event_type, message,
             logger=self.name,
             level=level,
             template=msg,
             args=args,
             **kwargs)
    
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message."""
        self.log(DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message."""
        self.log(INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message."""
        self.log(WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log error message."""
        self.log(ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message."""
        self.log(CRITICAL, msg, *args, **kwargs)


def get_logger(name: str = '') -> Logger:
    """
    Get or create logger by name.
    
    Creates a hierarchical logger structure where child loggers
    inherit configuration from parents.
    
    Args:
        name: Logger name (empty string for root logger)
        
    Returns:
        Logger instance
    """
    global _root_logger
    
    # Root logger special case
    if not name:
        if _root_logger is None:
            _root_logger = Logger('')
            _loggers[''] = _root_logger
        return _root_logger
    
    # Return existing logger
    if name in _loggers:
        return _loggers[name]
    
    # Find parent by traversing hierarchy
    parent = None
    parts = name.split('.')
    
    # Search for nearest parent
    for i in range(len(parts) - 1, -1, -1):
        parent_name = '.'.join(parts[:i])
        if parent_name in _loggers:
            parent = _loggers[parent_name]
            break
    
    # Use root as parent if no other parent found
    if parent is None:
        parent = get_logger('')  # Get or create root
    
    # Create new logger
    logger = Logger(name, parent)
    _loggers[name] = logger
    return logger


def create_log_formatter(
    format: str = "%(timestamp)s [%(level)s] %(logger)s: %(message)s",
    timestamp_format: str = "relative"
) -> Any:
    """
    Create a formatting handler for log events.
    
    Args:
        format: Message format template
        timestamp_format: 'relative' for ms since start, 'absolute' for wall clock
        
    Returns:
        Event handler that formats log events
    """
    # Level names for formatting
    level_names = {
        CRITICAL: 'CRITICAL',
        ERROR: 'ERROR',
        WARNING: 'WARNING',
        INFO: 'INFO',
        DEBUG: 'DEBUG',
    }
    
    def format_handler(event: Dict[str, Any]) -> None:
        # Only process log events
        if not event['type'].startswith(LOG_PREFIX):
            return
        
        # Extract fields
        level = event.get('level', 0)
        logger = event.get('logger', 'root')
        message = event['value']
        
        # Format timestamp
        if timestamp_format == 'relative':
            timestamp_ns = event.get('timestamp_ns', 0)
            timestamp = f"{timestamp_ns / 1_000_000:.1f}ms"
        else:
            import time
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Build format dict
        format_dict = {
            'timestamp': timestamp,
            'level': level_names.get(level, f'LEVEL{level}'),
            'logger': logger,
            'message': message,
        }
        
        # Format and print
        try:
            output = format % format_dict
        except (KeyError, ValueError):
            output = f"Format error: {format!r} with {format_dict!r}"
        
        print(output)
    
    format_handler.__name__ = f"log_formatter({format!r})"
    return format_handler


# Public exports
__all__ = [
    # Logger access
    'get_logger',
    'Logger',
    
    # Severity levels
    'CRITICAL',
    'ERROR', 
    'WARNING',
    'INFO',
    'DEBUG',
    'NOTSET',
    
    # Handlers
    'create_log_formatter',
]