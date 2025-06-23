"""
# Logging Domain

A structured message recording system that translates traditional log calls into events
flowing through the observability pipeline. The domain provides hierarchical loggers
with severity-based filtering while maintaining zero overhead for disabled log levels.

## Mental Model

The logging domain acts as an event producer that converts log operations into structured events:

```
Logger API Call → Event Generation → Handler Tree Processing
                                          ├─→ File (all messages)
                                          ├─→ Alert (errors only)
                                          └─→ Metrics (count by level)
```

This separation enables sophisticated log processing where the same log message can be
simultaneously written to files, trigger alerts, update dashboards, or feed analytics
systems - all without the logger knowing or caring about these destinations.

## Architecture

Loggers form a dot-separated hierarchy that mirrors application structure:

```
root
├── app
│   ├── app.database
│   ├── app.cache
│   └── app.api
└── library
    └── library.parser
```

Child loggers inherit configuration from parents, enabling granular control over log
verbosity across different subsystems.
"""

from typing import Any, Dict, Final

from ..core import ObservabilityContext

# Severity levels as constants
CRITICAL: Final[int] = 50
ERROR: Final[int] = 40
WARNING: Final[int] = 30
INFO: Final[int] = 20
DEBUG: Final[int] = 10

# Pre-computed event types for zero allocation
LOG_50: Final[str] = "log.50"  # CRITICAL
LOG_40: Final[str] = "log.40"  # ERROR
LOG_30: Final[str] = "log.30"  # WARNING
LOG_20: Final[str] = "log.20"  # INFO
LOG_10: Final[str] = "log.10"  # DEBUG

# Map levels to event types
LEVEL_TO_EVENT: Final[Dict[int, str]] = {
  CRITICAL: LOG_50,
  ERROR: LOG_40,
  WARNING: LOG_30,
  INFO: LOG_20,
  DEBUG: LOG_10,
}


class Logger:
  """
  Named logger that emits structured log events.

  Provides familiar logging API while producing events that flow through
  the observability pipeline. Message formatting is deferred until a
  handler actually processes the event.
  """

  __slots__ = ("_name", "_context", "_min_level")

  def __init__(self, name: str, context: ObservabilityContext, min_level: int = DEBUG):
    """
    Initialize logger.

    Args:
        name: Logger name for hierarchy
        context: ObservabilityContext to emit through
        min_level: Minimum severity to emit (default: DEBUG)
    """
    self._name = name
    self._context = context
    self._min_level = min_level

  def _log(self, level: int, msg: Any, args: tuple = (), **kwargs: Any) -> None:
    """
    Core logging implementation.

    Args:
        level: Severity level
        msg: Message object (usually string)
        args: Positional arguments for formatting
        **kwargs: Additional event metadata
    """
    # Early exit for performance
    if level < self._min_level:
      return

    if not self._context.has_handlers():
      return

    # Get pre-computed event type
    event_type = LEVEL_TO_EVENT.get(level, f"log.{level}")

    # Emit structured event
    self._context.emit(event_type, msg, logger=self._name, level=level, args=args, **kwargs)

  def debug(self, msg: Any, *args, **kwargs: Any) -> None:
    """Log a debug message."""
    self._log(DEBUG, msg, args, **kwargs)

  def info(self, msg: Any, *args, **kwargs: Any) -> None:
    """Log an info message."""
    self._log(INFO, msg, args, **kwargs)

  def warning(self, msg: Any, *args, **kwargs: Any) -> None:
    """Log a warning message."""
    self._log(WARNING, msg, args, **kwargs)

  def error(self, msg: Any, *args, **kwargs: Any) -> None:
    """Log an error message."""
    self._log(ERROR, msg, args, **kwargs)

  def critical(self, msg: Any, *args, **kwargs: Any) -> None:
    """Log a critical message."""
    self._log(CRITICAL, msg, args, **kwargs)

  def log(self, level: int, msg: Any, *args, **kwargs: Any) -> None:
    """Log a message at the specified level."""
    self._log(level, msg, args, **kwargs)

  def setLevel(self, level: int) -> None:
    """
    Set minimum logging level.

    Args:
        level: Minimum severity to emit
    """
    self._min_level = level

  def getChild(self, suffix: str) -> "Logger":
    """
    Get a child logger with extended name.

    Args:
        suffix: Name component to append

    Returns:
        Child logger instance
    """
    child_name = f"{self._name}.{suffix}"
    return Logger(child_name, self._context, self._min_level)
