"""
Lexer Builder Framework

A declarative framework for building lexical analyzers with stateful pattern 
recognition and automatic lifecycle management.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Iterator, Generic, TypeVar, Union
from abc import ABC, abstractmethod
from contextlib import contextmanager


# ===== Core Data Structures =====

@dataclass
class Position:
    """Represents a position in source text with line and column tracking."""
    offset: int
    line: int
    column: int


@dataclass
class Token:
    """
    Represents a lexical token with type, value, and position information.
    
    Attributes:
        type: The token type (e.g., 'IDENTIFIER', 'NUMBER')
        value: The actual text content of the token
        start: Starting offset in source text
        end: Ending offset in source text
        position: Line and column position information
    """
    type: str
    value: str
    start: int
    end: int
    position: Position
    
    @property
    def length(self) -> int:
        """Calculate token length from start and end positions."""
        return self.end - self.start
    
    def __repr__(self) -> str:
        return f"Token({self.type}, {repr(self.value)}, {self.position.line}, {self.position.column})"


@dataclass 
class Match:
    """Represents a successful pattern match result."""
    value: str
    length: int


class LexError(Exception):
    """
    Enhanced exception for lexical analysis errors with position tracking.
    
    Automatically formats error messages with line/column information and
    provides visual indication of error location in source code.
    """
    def __init__(self, message: str, position: Optional[Position] = None, source: Optional[str] = None):
        self.position = position
        self.source = source
        
        if position:
            location = f" at line {position.line}, column {position.column}"
            message = f"{message}{location}"
            
            if source:
                lines = source.split('\n')
                if 0 <= position.line - 1 < len(lines):
                    line_text = lines[position.line - 1]
                    pointer = ' ' * (position.column - 1) + '^'
                    message += f"\n{line_text}\n{pointer}"
        
        super().__init__(message)


# ===== State Management System =====

T = TypeVar('T')


class StateContainer(Generic[T]):
    """
    Base class for state containers that hold mutable state during lexing.
    
    Provides basic get/set/reset operations with type safety through generics.
    """
    def __init__(self, initial: T):
        self._value = initial
        self._initial = initial
    
    @property
    def value(self) -> T:
        """Current state value."""
        return self._value
    
    def get(self) -> T:
        """Get current value."""
        return self._value
    
    def set(self, value: T) -> None:
        """Update state value."""
        self._value = value
    
    def reset(self) -> None:
        """Reset to initial value."""
        self._value = self._initial
    
    def __eq__(self, other) -> bool:
        """Enable equality comparison with values."""
        if isinstance(other, StateContainer):
            return self._value == other._value
        return self._value == other
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value})"


class StackState(StateContainer[List]):
    """
    Stack-based state container for managing nested contexts.
    
    Useful for tracking indentation levels, nested scopes, or any
    hierarchical state that follows LIFO semantics.
    """
    def __init__(self, initial=None):
        super().__init__(initial or [])
    
    @property
    def current(self):
        """Get top of stack without removing."""
        return self._value[-1] if self._value else None
    
    @property
    def depth(self) -> int:
        """Get current stack depth."""
        return len(self._value)
    
    def push(self, item) -> None:
        """Push item onto stack."""
        self._value.append(item)
    
    def pop(self):
        """Pop and return top item from stack."""
        if self._value:
            return self._value.pop()
        return None
    
    def peek(self, index: int = -1):
        """Look at stack item without removing."""
        if abs(index) <= len(self._value):
            return self._value[index]
        return None
    
    def __contains__(self, item) -> bool:
        """Check if item exists in stack."""
        return item in self._value
    
    def __len__(self) -> int:
        """Get stack size."""
        return len(self._value)


class CounterState(StateContainer[int]):
    """
    Counter state container for tracking numeric values.
    
    Ideal for tracking bracket depth, occurrence counts, or any
    incrementable/decrementable state.
    """
    def __init__(self, initial: int = 0):
        super().__init__(initial)
    
    def increment(self, amount: int = 1) -> int:
        """Increment counter and return new value."""
        self._value += amount
        return self._value
    
    def decrement(self, amount: int = 1) -> int:
        """Decrement counter and return new value."""
        self._value -= amount
        return self._value
    
    def __int__(self) -> int:
        """Convert to integer."""
        return self._value
    
    def __add__(self, other: int) -> int:
        """Support addition operations."""
        return self._value + other
    
    def __sub__(self, other: int) -> int:
        """Support subtraction operations."""
        return self._value - other


class SetState(StateContainer[set]):
    """
    Set-based state container for tracking unique values.
    
    Useful for maintaining dynamic symbol tables, tracking seen tokens,
    or managing collections of unique identifiers.
    """
    def __init__(self, initial=None):
        super().__init__(initial or set())
    
    def add(self, item) -> None:
        """Add item to set."""
        self._value.add(item)
    
    def remove(self, item) -> None:
        """Remove item from set (no error if missing)."""
        self._value.discard(item)
    
    def __contains__(self, item) -> bool:
        """Check membership."""
        return item in self._value
    
    def __len__(self) -> int:
        """Get set size."""
        return len(self._value)


class StateFactory:
    """Factory for creating typed state containers."""
    
    def __call__(self, initial_value=None) -> StateContainer:
        """Create simple state container."""
        return StateContainer(initial_value)
    
    def stack(self, initial=None) -> StackState:
        """Create stack state container."""
        return StackState(initial)
    
    def counter(self, initial: int = 0) -> CounterState:
        """Create counter state container."""
        return CounterState(initial)
    
    def set(self, initial=None) -> SetState:
        """Create set state container."""
        return SetState(initial)


# Singleton state factory instance
State = StateFactory()


# ===== Token Stream Processing =====

class TokenStream:
    """
    Character stream with position tracking for lexical analysis.
    
    Provides efficient character-level access with automatic position
    tracking, lookahead capabilities, and error reporting.
    """
    
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.mark_stack = []
        self.line_starts = self._find_line_starts()
    
    def _find_line_starts(self) -> List[int]:
        """Precompute line start positions for efficient lookup."""
        starts = [0]
        for i, char in enumerate(self.text):
            if char == '\n':
                starts.append(i + 1)
        return starts
    
    @property
    def at_line_start(self) -> bool:
        """Check if current position is at start of a line."""
        return self.pos in self.line_starts
    
    @property
    def current_position(self) -> Position:
        """Get current position information."""
        return Position(self.pos, self.line, self.column)
    
    def peek(self, offset: int = 0) -> Optional[str]:
        """Look ahead at character without consuming."""
        idx = self.pos + offset
        return self.text[idx] if idx < len(self.text) else None
    
    def advance(self, count: int = 1) -> None:
        """Move position forward with line/column tracking."""
        for _ in range(count):
            if self.pos < len(self.text):
                if self.text[self.pos] == '\n':
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1
    
    def match(self, text: str) -> bool:
        """Try to match text at current position."""
        end = self.pos + len(text)
        if end <= len(self.text) and self.text[self.pos:end] == text:
            self.advance(len(text))
            return True
        return False
    
    def match_while(self, predicate: Callable[[str], bool]) -> str:
        """Consume characters while predicate is true."""
        start = self.pos
        while self.pos < len(self.text) and predicate(self.text[self.pos]):
            self.advance()
        return self.text[start:self.pos]
    
    def match_word(self) -> Optional[str]:
        """Match identifier-like word pattern."""
        if self.pos < len(self.text) and self.text[self.pos].isalpha():
            return self.match_while(lambda c: c.isalnum() or c == '_')
        return None
    
    def mark(self) -> None:
        """Save current position for potential backtracking."""
        self.mark_stack.append((self.pos, self.line, self.column))
    
    def reset(self) -> None:
        """Restore to last marked position."""
        if self.mark_stack:
            self.pos, self.line, self.column = self.mark_stack.pop()
    
    def capture(self) -> str:
        """Get text from last mark to current position."""
        if self.mark_stack:
            start, _, _ = self.mark_stack.pop()
            return self.text[start:self.pos]
        return ""
    
    def at_end(self) -> bool:
        """Check if at end of stream."""
        return self.pos >= len(self.text)
    
    def error(self, message: str) -> None:
        """Raise error with position context."""
        raise LexError(message, position=self.current_position, source=self.text)


# ===== Pattern Matching System =====

class Matcher(ABC):
    """Abstract base class for pattern matching strategies."""
    
    @abstractmethod
    def match(self, stream: TokenStream) -> Optional[Match]:
        """Attempt to match pattern at current stream position."""
        pass


class RegexMatcher(Matcher):
    """Pattern matcher using regular expressions."""
    
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex = re.compile(pattern)
    
    def match(self, stream: TokenStream) -> Optional[Match]:
        """Match regex pattern at current position."""
        match = self.regex.match(stream.text, stream.pos)
        if match:
            return Match(match.group(0), match.end() - match.start())
        return None


class LiteralMatcher(Matcher):
    """Pattern matcher for exact string literals."""
    
    def __init__(self, literal: str):
        self.literal = literal
    
    def match(self, stream: TokenStream) -> Optional[Match]:
        """Match exact literal at current position."""
        if stream.text[stream.pos:].startswith(self.literal):
            return Match(self.literal, len(self.literal))
        return None


class MethodMatcher(Matcher):
    """Pattern matcher using custom method logic."""
    
    def __init__(self, method: Callable):
        self.method = method
        self.line_start_only = getattr(method, '_line_start_only', False)
        self.when_condition = getattr(method, '_when_condition', None)
    
    def match(self, stream: TokenStream) -> Optional[Match]:
        """Execute method to match pattern."""
        # Check line position constraint
        if self.line_start_only and not stream.at_line_start:
            return None
        
        instance = getattr(stream, '_lexer_instance', None)
        
        # Check when condition
        if self.when_condition and instance:
            if not self.when_condition(instance):
                return None
        
        # Mark position for capture
        stream.mark()
        
        try:
            result = self.method(instance, stream)
            
            if result:
                # Method should have advanced stream
                length = stream.pos - stream.mark_stack[-1][0]
                value = stream.capture()
                
                # Handle different return types
                if isinstance(result, Token):
                    return TokenMatch(result)
                elif isinstance(result, list):
                    return MultiTokenMatch(result)
                else:
                    return Match(value, length)
            else:
                stream.reset()
                return None
        except Exception as e:
            stream.reset()
            if isinstance(e, LexError):
                raise
            raise LexError(str(e), position=stream.current_position, source=stream.text)


class TokenMatch(Match):
    """Match result containing a complete token."""
    def __init__(self, token: Token):
        self.token = token
        super().__init__(token.value, token.end - token.start)


class MultiTokenMatch(Match):
    """Match result containing multiple tokens."""
    def __init__(self, tokens: Union[List[Token], Token]):
        self.tokens = tokens if isinstance(tokens, list) else [tokens]
        # Calculate total length
        if self.tokens:
            length = self.tokens[-1].end - self.tokens[0].start
            value = ''  # Not used for multi-token
        else:
            length = 0
            value = ''
        super().__init__(value, length)


# ===== Token Definition =====

class TokenDefinition:
    """
    Defines a token pattern with associated metadata.
    
    Combines a pattern matcher with priority, skip behavior, and
    context information to fully specify token recognition rules.
    """
    
    def __init__(self, name: str, matcher: Matcher, 
                 priority: int = 0, skip: bool = False, 
                 context: str = 'default'):
        self.name = name
        self.matcher = matcher
        self.priority = priority
        self.skip = skip
        self.context = context
    
    def match(self, stream: TokenStream) -> Optional[Match]:
        """Execute matcher against stream."""
        return self.matcher.match(stream)


# ===== Token Factory =====

class TokenFactory:
    """Factory for creating token definitions with various pattern types."""
    
    def __call__(self, func: Callable = None, *, 
                 priority: int = 0, skip: bool = False, 
                 context: str = 'default', when: Optional[Callable] = None):
        """
        Decorator for method-based token patterns.
        
        Args:
            func: The method to decorate
            priority: Token matching priority (higher = earlier)
            skip: Whether to skip this token in output
            context: Lexer context where token is active
            when: Condition function for token activation
        """
        def wrapper(func):
            if when:
                func._when_condition = when
            matcher = MethodMatcher(func)
            return TokenDefinition(func.__name__, matcher, priority, skip, context)
        
        if func is None:
            return wrapper
        return wrapper(func)
    
    def regex(self, pattern: str, **kwargs):
        """Create regex-based token pattern."""
        matcher = RegexMatcher(pattern)
        return TokenDefinition(None, matcher, **kwargs)
    
    def literal(self, value: str, **kwargs):
        """Create literal string token pattern."""
        matcher = LiteralMatcher(value)
        return TokenDefinition(None, matcher, **kwargs)
    
    def at_line_start(self, func: Callable = None, **kwargs):
        """Decorator for tokens that only match at line start."""
        def wrapper(func):
            func._line_start_only = True
            return self.__call__(func, **kwargs)
        
        if func is None:
            return wrapper
        return wrapper(func)
    
    def when(self, condition: Callable):
        """Create conditional token decorator."""
        def decorator(func: Callable = None, **kwargs):
            kwargs['when'] = condition
            return self.__call__(func, **kwargs)
        return decorator


# Create singleton factory instance
token = TokenFactory()


# ===== State Descriptor =====

class StateDescriptor:
    """Descriptor for per-instance state containers."""
    def __init__(self, state_container):
        self.state_container = state_container
        self.name = None
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        # Create state instance if it doesn't exist
        state_key = f'_state_{self.name}'
        if not hasattr(obj, state_key):
            setattr(obj, state_key, self.state_container)
        return getattr(obj, state_key)
    
    def __set__(self, obj, value):
        # Allow setting the state value directly
        state = self.__get__(obj)
        state.set(value)


# ===== Lexing Context Manager =====

class LexingContext:
    """
    Context manager for lexical analysis lifecycle.
    
    Handles state reset, error enhancement, and final token generation
    through Python's context manager protocol.
    """
    
    def __init__(self, lexer, text: str):
        self.lexer = lexer
        self.original_text = text
        self.text = text
        self.final_tokens = []
        self.stream = None
    
    def __enter__(self):
        # Reset all state containers
        for attr_name in self.lexer._state_attrs:
            getattr(self.lexer, attr_name).reset()
        
        # Normalize text
        if self.text and not self.text.endswith('\n'):
            self.text += '\n'
        
        # Create stream
        self.stream = TokenStream(self.text)
        self.stream._lexer_instance = self.lexer
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and isinstance(exc_val, LexError):
            # Enhance error with state context
            state_info = []
            
            # Check common state containers
            for attr_name, label in [
                ('bracket_depth', 'brackets'),
                ('paren_depth', 'parentheses'),
                ('brace_depth', 'braces')
            ]:
                if hasattr(self.lexer, attr_name):
                    depth = getattr(self.lexer, attr_name).value
                    if depth != 0:
                        state_info.append(f"unclosed {label}: {depth}")
            
            if state_info:
                exc_val.args = (f"{exc_val.args[0]} ({', '.join(state_info)})",)
        
        elif not exc_type:
            # Generate final tokens on successful completion
            pos = len(self.text)
            position = Position(pos, self.text.count('\n'), 1)
            
            # Handle remaining indentation
            if hasattr(self.lexer, 'indent_stack'):
                while self.lexer.indent_stack.depth > 1:
                    self.lexer.indent_stack.pop()
                    self.final_tokens.append(
                        Token('DEDENT', '', pos, pos, position)
                    )
            
            # Add end marker
            self.final_tokens.append(
                Token('ENDMARKER', '', pos, pos, position)
            )
        
        # Don't suppress exceptions
        return False


# ===== Token Match Information =====

@dataclass
class TokenMatchInfo:
    """Internal representation of token match results."""
    definition: TokenDefinition
    value: str
    start: int
    end: int
    position: Position
    tokens: Optional[List[Token]] = None
    
    @property
    def name(self):
        return self.definition.name
    
    @property
    def skip(self):
        return self.definition.skip


# ===== Lexer Metaclass =====

class LexerMeta(type):
    """
    Metaclass for lexer classes.
    
    Collects token definitions and state declarations from class
    attributes and prepares them for efficient lexical analysis.
    """
    
    def __new__(cls, name, bases, namespace):
        definitions = []
        state_attrs = {}
        
        # Collect token definitions and state
        for attr_name, attr_value in list(namespace.items()):
            if isinstance(attr_value, TokenDefinition):
                # Set name for attribute-based tokens
                if attr_value.name is None:
                    attr_value.name = attr_name
                definitions.append(attr_value)
                del namespace[attr_name]
            elif isinstance(attr_value, StateContainer):
                # Convert state containers to descriptors
                namespace[attr_name] = StateDescriptor(attr_value)
                state_attrs[attr_name] = attr_value
        
        # Sort by priority (highest first)
        definitions.sort(key=lambda d: d.priority, reverse=True)
        
        namespace['_token_definitions'] = definitions
        namespace['_state_attrs'] = state_attrs
        
        return super().__new__(cls, name, bases, namespace)


# ===== Base Lexer Class =====

class Lexer(metaclass=LexerMeta):
    """
    Base class for lexical analyzers.
    
    Subclass this to create custom lexers by defining token patterns
    as class attributes and methods.
    """
    
    def __init__(self):
        self.contexts = ['default']
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Optimize patterns for execution."""
        self.regex_patterns = []
        self.other_patterns = []
        
        for defn in self._token_definitions:
            if isinstance(defn.matcher, RegexMatcher):
                self.regex_patterns.append(defn)
            else:
                self.other_patterns.append(defn)
        
        if self.regex_patterns:
            self._compile_master_regex()
    
    def _compile_master_regex(self):
        """Compile all regex patterns into single master regex."""
        pattern_parts = []
        self.group_to_definition = {}
        
        for i, defn in enumerate(self.regex_patterns):
            group_name = f'g{i}'
            pattern_parts.append(f'(?P<{group_name}>{defn.matcher.pattern})')
            self.group_to_definition[group_name] = defn
        
        self.master_regex = re.compile('|'.join(pattern_parts))
    
    def lex(self, text: str) -> Iterator[Token]:
        """
        Perform lexical analysis on input text.
        
        Args:
            text: Source text to analyze
            
        Yields:
            Token objects in sequence
            
        Raises:
            LexError: On invalid input
        """
        with LexingContext(self, text) as ctx:
            # Main lexing loop
            while not ctx.stream.at_end():
                token_match = self._next_token(ctx.stream)
                if token_match:
                    # Handle multi-token returns
                    if hasattr(token_match, 'tokens') and token_match.tokens:
                        yield from token_match.tokens
                    elif not token_match.skip:
                        yield Token(
                            token_match.name,
                            token_match.value,
                            token_match.start,
                            token_match.end,
                            token_match.position
                        )
            
            # Yield final tokens from context
            yield from ctx.final_tokens
    
    def _next_token(self, stream: TokenStream) -> Optional[TokenMatchInfo]:
        """Find next token at current position."""
        start_pos = stream.pos
        start_position = stream.current_position
        
        # Try master regex first for performance
        if hasattr(self, 'master_regex'):
            match = self.master_regex.match(stream.text, stream.pos)
            if match:
                group_name = match.lastgroup
                defn = self.group_to_definition[group_name]
                
                if defn.context == self.contexts[-1]:
                    stream.advance(match.end() - match.start())
                    return TokenMatchInfo(defn, match.group(), start_pos, stream.pos, start_position)
        
        # Try other patterns
        for defn in self._get_active_patterns():
            if match := defn.match(stream):
                # Handle different match types
                if isinstance(match, TokenMatch):
                    stream.advance(match.length)
                    return TokenMatchInfo(defn, match.token.value, start_pos, stream.pos, 
                                       start_position, tokens=[match.token])
                elif isinstance(match, MultiTokenMatch):
                    stream.advance(match.length)
                    return TokenMatchInfo(defn, '', start_pos, stream.pos, 
                                       start_position, tokens=match.tokens)
                else:
                    stream.advance(match.length)
                    return TokenMatchInfo(defn, match.value, start_pos, stream.pos, start_position)
        
        # No match - error
        char = stream.peek()
        stream.error(f"Unexpected character '{char}'")
    
    def _get_active_patterns(self):
        """Get patterns for current context."""
        current_context = self.contexts[-1]
        return [
            defn for defn in self._token_definitions
            if defn.context == current_context
        ]
    
    def push_context(self, context: str):
        """Enter new lexing context."""
        self.contexts.append(context)
    
    def pop_context(self):
        """Exit current context."""
        if len(self.contexts) > 1:
            self.contexts.pop()

