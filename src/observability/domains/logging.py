"""
# Logging Domain

A structured message recording system that translates traditional log calls into events flowing through the observability pipeline. The domain provides hierarchical loggers with severity-based filtering while maintaining zero overhead for disabled log levels.

## Mental Model

The logging domain acts as an event producer that converts log operations into structured events:

```
Logger API Call → Event Generation → Handler Tree Processing
                                          ├─→ File (all messages)
                                          ├─→ Alert (errors only)
                                          └─→ Metrics (count by level)
```

This separation enables sophisticated log processing where the same log message can be simultaneously written to files, trigger alerts, update dashboards, or feed analytics systems - all without the logger knowing or caring about these destinations.

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

Child loggers inherit configuration from parents, enabling granular control over log verbosity across different subsystems.

## Key Concepts

**Logger Hierarchy**: Named loggers that inherit thresholds from ancestors, allowing centralized configuration with local overrides.

**Severity Levels**: Numeric thresholds that control event emission:
- CRITICAL (50): System failures requiring immediate attention
- ERROR (40): Recoverable failures affecting operations
- WARNING (30): Concerning but non-critical conditions
- INFO (20): Standard operational messages
- DEBUG (10): Detailed diagnostic information

**Lazy Evaluation**: Message formatting occurs only when the severity threshold is met, eliminating string construction overhead for disabled levels.

**Structured Events**: Log calls generate events with consistent schema:
```python
{
    "type": "log.{severity}",     # Pre-computed for performance
    "value": formatted_message,    # Final formatted string
    "logger": logger_name,         # Hierarchical name
    "level": numeric_level,        # For filtering
    "template": format_string,     # Original template
    "args": positional_args,       # Template arguments
    **context_variables,           # Automatic enrichment
    **extra_fields                 # User-provided metadata
}
```

## Performance Characteristics

The domain achieves zero overhead through threshold pre-filtering:

```python
if not logger.is_enabled_for(level):
    return  # No event construction or formatting
```

When enabled, performance costs include:
- Severity check: ~10ns
- Event construction: ~100ns
- String formatting: Variable based on complexity

## Design Principles

- **Hierarchical Control**: Configure once at the root, override where needed
- **Zero-Cost Filtering**: Disabled levels incur only a numeric comparison
- **Fail-Safe Formatting**: Template errors produce diagnostic messages, not crashes
- **Transparent Context**: Automatic inclusion of trace IDs and request context

The logging domain transforms familiar logging patterns into a powerful event stream, enabling sophisticated observability workflows while maintaining the simplicity developers expect.
"""

import os
import sys
import time
import weakref
from typing import Any, Dict, Final, Optional, TextIO

from ..core import emit, has_handlers
from ..types import EventDict, EventHandler

# Event type prefix for all logging events
LOG_PREFIX: Final[str] = "log"

# Severity levels as numeric thresholds
CRITICAL: Final[int] = 50
ERROR: Final[int] = 40
WARNING: Final[int] = 30
INFO: Final[int] = 20
DEBUG: Final[int] = 10
NOTSET: Final[int] = 0

# Pre-computed event types for performance
EVENT_TYPES: Final[Dict[int, str]] = {
  CRITICAL: f"{LOG_PREFIX}.{CRITICAL}",
  ERROR: f"{LOG_PREFIX}.{ERROR}",
  WARNING: f"{LOG_PREFIX}.{WARNING}",
  INFO: f"{LOG_PREFIX}.{INFO}",
  DEBUG: f"{LOG_PREFIX}.{DEBUG}",
}

# Human-readable severity names
LEVEL_NAMES: Final[Dict[int, str]] = {
  CRITICAL: "CRITICAL",
  ERROR: "ERROR",
  WARNING: "WARNING",
  INFO: "INFO",
  DEBUG: "DEBUG",
}

# Logger hierarchy storage
_registry: Dict[str, "Logger"] = {}
_root: Optional["Logger"] = None


class Logger:
  """
  Hierarchical event emitter with severity-based filtering.

  Loggers form a dot-separated hierarchy where children inherit
  configuration from parents. Events emit only when severity
  thresholds are met, ensuring zero overhead for disabled levels.
  """

  __slots__ = ("name", "level", "_parent_ref")

  def __init__(self, name: str, parent: Optional["Logger"] = None):
    """
    Initialize logger within hierarchy.

    Args:
        name: Dot-separated hierarchical name
        parent: Parent logger for configuration inheritance
    """
    self.name = name
    self.level = NOTSET
    self._parent_ref = weakref.ref(parent) if parent else None

  @property
  def effective_level(self) -> int:
    """Resolve effective severity threshold through hierarchy."""
    if self.level != NOTSET:
      return self.level

    parent = self._parent_ref() if self._parent_ref else None
    if parent:
      return parent.effective_level

    return WARNING  # Default threshold

  def set_level(self, level: int) -> None:
    """Configure severity threshold for this logger."""
    self.level = level

  def is_enabled_for(self, level: int) -> bool:
    """
    Check if severity level would emit an event.

    Zero-cost rejection path when no handlers attached.
    """
    return has_handlers() and level >= self.effective_level

  def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
    """
    Emit log event at specified severity.

    Message formatting occurs only when severity threshold is met,
    providing lazy evaluation for performance.

    Args:
        level: Numeric severity level
        msg: Message template using % formatting
        *args: Positional arguments for template
        **kwargs: Extra fields added to event
    """
    if not self.is_enabled_for(level):
      return

    # Lazy message formatting
    if args:
      try:
        message = msg % args
      except (TypeError, ValueError) as e:
        message = f"Format error: {msg!r} % {args!r} - {e}"
    else:
      message = msg

    # Emit structured event
    event_type = EVENT_TYPES.get(level, f"{LOG_PREFIX}.{level}")
    emit(event_type, message, logger=self.name, level=level, template=msg, args=args, **kwargs)

  def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
    """Emit debug-level event."""
    self.log(DEBUG, msg, *args, **kwargs)

  def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
    """Emit info-level event."""
    self.log(INFO, msg, *args, **kwargs)

  def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
    """Emit warning-level event."""
    self.log(WARNING, msg, *args, **kwargs)

  def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
    """Emit error-level event."""
    self.log(ERROR, msg, *args, **kwargs)

  def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
    """Emit critical-level event."""
    self.log(CRITICAL, msg, *args, **kwargs)


def get_logger(name: str = "") -> Logger:
  """
  Retrieve or create logger within hierarchy.

  Logger hierarchy uses dot notation where children inherit
  configuration from ancestors. Empty string returns root logger.

  Args:
      name: Hierarchical logger name

  Returns:
      Logger instance
  """
  global _root

  # Root logger singleton
  if not name:
    if _root is None:
      _root = Logger("")
      _registry[""] = _root
    return _root

  # Return existing logger
  if name in _registry:
    return _registry[name]

  # Find parent through hierarchy traversal
  parent = None
  parts = name.split(".")

  for i in range(len(parts) - 1, -1, -1):
    parent_name = ".".join(parts[:i])
    if parent_name in _registry:
      parent = _registry[parent_name]
      break

  # Default to root if no parent found
  if parent is None:
    parent = get_logger("")

  # Create and register logger
  logger = Logger(name, parent)
  _registry[name] = logger
  return logger


# Color support for formatters
class Colors:
  """ANSI escape sequences for terminal formatting."""

  # Colors
  RED = "\033[91m"
  YELLOW = "\033[93m"
  GREEN = "\033[92m"
  BLUE = "\033[94m"
  CYAN = "\033[96m"
  GRAY = "\033[90m"

  # Styles
  BOLD = "\033[1m"
  DIM = "\033[2m"

  # Reset
  RESET = "\033[0m"


def _supports_color(stream: TextIO = sys.stdout) -> bool:
  """
  Detect terminal color support.

  Respects NO_COLOR environment variable and checks terminal
  capabilities across platforms.
  """
  if os.environ.get("NO_COLOR"):
    return False

  if not hasattr(stream, "isatty") or not stream.isatty():
    return False

  term = os.environ.get("TERM", "")
  if term == "dumb":
    return False

  if sys.platform == "win32":
    return os.environ.get("ANSICON") or "WT_SESSION" in os.environ

  return True


def formatter(
  format: str = "%(timestamp)s [%(level)s] %(logger)s: %(message)s",
  *,
  timestamp_format: str = "relative",
  colorize: Optional[bool] = None,
  stream: TextIO = sys.stdout,
) -> EventHandler:
  """
  Create log event formatter with optional color support.

  Formats log events for human consumption with configurable
  timestamp formats and automatic color detection.

  Args:
      format: Template with %(field)s placeholders
      timestamp_format: "relative" (ms since start) or "absolute" (wall clock)
      colorize: Enable colors (None=auto-detect)
      stream: Output stream for color detection

  Returns:
      Event handler that formats log events
  """
  # Auto-detect color support
  if colorize is None:
    colorize = _supports_color(stream)

  # Color mappings for severity levels
  level_colors = {
    CRITICAL: Colors.RED + Colors.BOLD,
    ERROR: Colors.RED,
    WARNING: Colors.YELLOW,
    INFO: Colors.GREEN,
    DEBUG: Colors.CYAN,
  }

  def handler(event: EventDict) -> None:
    # Filter non-log events
    if not event["type"].startswith(LOG_PREFIX):
      return

    # Extract event fields
    level = event.get("level", 0)
    logger_name = event.get("logger", "root")
    message = event["value"]

    # Format timestamp
    if timestamp_format == "relative":
      timestamp_ns = event.get("timestamp_ns", 0)
      timestamp = f"{timestamp_ns / 1_000_000:.1f}ms"
    else:
      timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # Apply colors if enabled
    if colorize:
      timestamp = f"{Colors.GRAY}{timestamp}{Colors.RESET}"
      logger_name = f"{Colors.BLUE}{logger_name}{Colors.RESET}"

      level_name = LEVEL_NAMES.get(level, f"LEVEL{level}")
      level_color = level_colors.get(level, "")
      level_str = f"{level_color}{level_name}{Colors.RESET}"
    else:
      level_str = LEVEL_NAMES.get(level, f"LEVEL{level}")

    # Build format dictionary
    format_dict = {
      "timestamp": timestamp,
      "level": level_str,
      "logger": logger_name,
      "message": message,
    }

    # Apply template and output
    try:
      output = format % format_dict
    except (KeyError, ValueError) as e:
      output = f"Format error: {format!r} - {e}"

    print(output, file=stream)

  handler.__name__ = f"log_formatter(colorize={colorize})"
  return handler


def minimal_formatter(*, colorize: Optional[bool] = None) -> EventHandler:
  """
  Create minimal formatter for development use.

  Shows only severity and message for reduced visual noise.
  """
  return formatter(format="%(level)s: %(message)s", colorize=colorize)


def json_formatter(*, stream: TextIO = sys.stdout) -> EventHandler:
  """
  Create structured JSON formatter.

  Outputs newline-delimited JSON for machine processing.
  """
  import json

  def handler(event: EventDict) -> None:
    if not event["type"].startswith(LOG_PREFIX):
      return

    # Convert to JSON-serializable format
    output = {
      "timestamp": event.get("timestamp_ns", 0) / 1_000_000,
      "level": LEVEL_NAMES.get(event.get("level", 0), "UNKNOWN"),
      "logger": event.get("logger", "root"),
      "message": event["value"],
    }

    # Add extra fields
    for key, value in event.items():
      if key not in {"type", "value", "timestamp_ns", "level", "logger", "template", "args"}:
        output[key] = value

    json.dump(output, stream, default=str)
    stream.write("\n")
    stream.flush()

  handler.__name__ = "json_formatter"
  return handler


# Public API
__all__ = [
  # Logger access
  "get_logger",
  "Logger",
  # Severity levels
  "CRITICAL",
  "ERROR",
  "WARNING",
  "INFO",
  "DEBUG",
  "NOTSET",
  # Formatters
  "formatter",
  "minimal_formatter",
  "json_formatter",
]
