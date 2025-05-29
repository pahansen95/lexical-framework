# Lexer Builder Framework

A declarative framework for building lexical analyzers in Python with stateful pattern recognition and automatic lifecycle management.

## Overview

The Lexer Builder Framework provides a Pythonic approach to constructing lexers through declarative pattern definitions, typed state management, and context-aware tokenization. The framework emphasizes developer productivity while maintaining performance suitable for production language implementations.

## Architecture

### Core Components

The framework consists of five primary architectural layers:

**Pattern Matching Layer**
- `Matcher` classes encapsulate pattern recognition strategies
- `RegexMatcher` for regular expression patterns
- `LiteralMatcher` for exact string matching
- `MethodMatcher` for complex procedural patterns

**Token Definition Layer**
- `TokenDefinition` binds patterns to token types
- Priority-based conflict resolution
- Conditional activation through `when` predicates
- Skip tokens for non-semantic elements

**State Management Layer**
- Typed state containers (`State.stack()`, `State.counter()`, `State.set()`)
- Automatic state reset between lexical analyses
- Observable state for debugging

**Stream Processing Layer**
- `TokenStream` provides position-aware character access
- Automatic line/column tracking
- Mark/reset capability for backtracking
- Enhanced error reporting with source context

**Lifecycle Management Layer**
- `TokenizationContext` manages lexer lifecycle through context managers
- Automatic final token generation
- Error enhancement with state information
- Guaranteed cleanup semantics

### Design Principles

**Declarative Pattern Definition**
Lexical patterns are defined declaratively, separating pattern specification from recognition mechanics.

**Stateful Recognition**
State containers provide first-class support for context-sensitive lexical analysis.

**Composable Architecture**
Components compose naturally through clear interfaces and separation of concerns.

**Production-Ready Defaults**
Sensible defaults for error handling, position tracking, and performance optimization.

## API Reference

### Lexer Definition

```python
class MyLexer(Lexer):
    # State declarations
    mode = State('normal')
    depth = State.counter(0)
    
    # Token patterns
    IDENTIFIER = token.regex(r'[a-zA-Z_]\w*', priority=10)
    NUMBER = token.regex(r'\d+', priority=5)
    
    # Method-based tokens
    @token(priority=20)
    def STRING(self, stream: TokenStream):
        # Complex pattern logic
        pass
```

### Token Factory

The `token` factory provides multiple pattern definition methods:

#### Regular Expression Patterns
```python
IDENTIFIER = token.regex(r'[a-zA-Z_]\w*', priority=10)
```

#### Literal Patterns
```python
PLUS = token.literal('+', priority=5)
```

#### Method Patterns
```python
@token(priority=15)
def COMPLEX_PATTERN(self, stream: TokenStream):
    # Custom matching logic
    return True  # Simple match
    return Token(...)  # Single token
    return [Token(...), Token(...)]  # Multiple tokens
```

### State Containers

#### Simple State
```python
mode = State('initial_value')
mode.get()  # Read value
mode.set('new_value')  # Update value
mode.reset()  # Restore initial value
```

#### Stack State
```python
indent_stack = State.stack([0])
indent_stack.push(4)  # Push new value
indent_stack.current  # Peek top value
indent_stack.pop()  # Remove top value
indent_stack.depth  # Stack size
```

#### Counter State
```python
bracket_depth = State.counter(0)
bracket_depth.increment()  # Add 1
bracket_depth.decrement()  # Subtract 1
bracket_depth.value  # Current count
```

#### Set State
```python
keywords = State.set({'if', 'else', 'while'})
'if' in keywords  # Membership test
keywords.add('for')  # Add element
keywords.remove('while')  # Remove element
```

### Conditional Patterns

#### Position-Based Conditions
```python
@token.at_line_start(priority=50)
def INDENTATION(self, stream: TokenStream):
    # Only matches at line beginning
    pass
```

#### State-Based Conditions
```python
@token.when(lambda self: self.bracket_depth == 0)
def SIGNIFICANT_WHITESPACE(self, stream: TokenStream):
    # Only active outside brackets
    pass
```

### Token Stream Operations

```python
stream.peek()  # Look ahead one character
stream.peek(2)  # Look ahead multiple characters
stream.advance()  # Consume one character
stream.advance(5)  # Consume multiple characters
stream.match('keyword')  # Try to match string
stream.match_while(str.isdigit)  # Match while condition true
stream.match_word()  # Match identifier pattern
stream.at_line_start  # Position check
stream.at_end()  # EOF check
stream.error('message')  # Raise error with position
```

## Usage Patterns

### Basic Lexer

```python
class JSONLexer(Lexer):
    # Simple patterns
    NUMBER = token.regex(r'-?\d+(\.\d+)?([eE][+-]?\d+)?')
    STRING = token.regex(r'"([^"\\]|\\.)*"')
    TRUE = token.literal('true')
    FALSE = token.literal('false')
    NULL = token.literal('null')
    
    # Structural tokens
    LBRACE = token.literal('{')
    RBRACE = token.literal('}')
    COMMA = token.literal(',')
    COLON = token.literal(':')
    
    # Skip whitespace
    WS = token.regex(r'\s+', skip=True)
```

### Stateful Lexer

```python
class TemplateLexer(Lexer):
    mode = State('text')
    
    @token.when(lambda self: self.mode == 'text')
    def TEXT(self, stream: TokenStream):
        # Capture until template marker
        start = stream.pos
        while not stream.at_end() and not stream.peek(2) == '{{':
            stream.advance()
        return stream.pos > start
    
    @token(priority=20)
    def TEMPLATE_START(self, stream: TokenStream):
        if stream.match('{{'):
            self.mode.set('template')
            return True
    
    @token.when(lambda self: self.mode == 'template')
    def VARIABLE(self, stream: TokenStream):
        return stream.match_word()
    
    @token(priority=20)
    def TEMPLATE_END(self, stream: TokenStream):
        if stream.match('}}'):
            self.mode.set('text')
            return True
```

### Indentation-Aware Lexer

```python
class PythonLexer(Lexer):
    indent_stack = State.stack([0])
    bracket_depth = State.counter(0)
    
    @token(priority=10)
    def LPAREN(self, stream: TokenStream):
        if stream.match('('):
            self.bracket_depth.increment()
            return True
    
    @token.when(lambda self: self.bracket_depth == 0)
    @token.at_line_start(priority=50)
    def INDENT_HANDLER(self, stream: TokenStream):
        spaces = len(stream.match_while(lambda c: c == ' '))
        
        if stream.peek() in ('\n', '#', None):
            return None  # Skip empty lines
        
        current = self.indent_stack.current
        
        if spaces > current:
            self.indent_stack.push(spaces)
            return Token('INDENT', '', stream.pos, stream.pos, stream.current_position)
        elif spaces < current:
            tokens = []
            while self.indent_stack.current > spaces:
                self.indent_stack.pop()
                tokens.append(Token('DEDENT', '', stream.pos, stream.pos, stream.current_position))
            return tokens
```

## Error Handling

The framework provides comprehensive error handling with automatic position tracking:

```python
# Automatic error enhancement
try:
    tokens = list(lexer.lex(source))
except TokenError as e:
    print(e)
    # Output: Unexpected character '}' at line 5, column 12
    # data = {1, 2, 3}
    #                ^
```

Context managers automatically enhance errors with state information:

```python
# Unclosed delimiters reported
TokenError: Unexpected end of input (unclosed brackets: 2, unclosed parentheses: 1)
```

## Performance Considerations

### Pattern Compilation

Regular expression patterns compile into a single master regex for optimal performance:
- O(1) token type identification through named groups
- Single regex match per position
- Automatic longest-match semantics

### State Operations

State containers provide efficient operations:
- O(1) access and updates for simple state
- O(1) stack operations
- Minimal allocation through value reuse

### Memory Management

The framework minimizes allocations through:
- Token object pooling (when applicable)
- Streaming processing without full tokenization
- Efficient position tracking

## Best Practices

### Pattern Organization

Order patterns by specificity and frequency:
1. Keywords and reserved words (highest priority)
2. Complex patterns (methods)
3. Operators (by length)
4. Identifiers and literals
5. Whitespace and comments (lowest priority)

### State Design

Use appropriate state containers:
- `State()` for simple flags and modes
- `State.stack()` for nested contexts
- `State.counter()` for balanced delimiters
- `State.set()` for dynamic symbol tables

### Error Recovery

Implement error tokens for robustness:
```python
@token(priority=0)
def ERROR(self, stream: TokenStream):
    char = stream.peek()
    stream.advance()
    stream.error(f"Unexpected character: {char}")
```

### Testing Patterns

Test lexers with comprehensive inputs:
- Valid token sequences
- Error conditions
- State transitions
- Performance characteristics

## Integration

### Basic Usage

```python
lexer = MyLexer()
tokens = list(lexer.lex(source_code))
```

### Streaming Usage

```python
lexer = MyLexer()
for token in lexer.lex(source_code):
    process(token)
```

### Parser Integration

```python
class Parser:
    def __init__(self, lexer):
        self.lexer = lexer
    
    def parse(self, source):
        self.tokens = self.lexer.lex(source)
        return self.parse_program()
```

## Advanced Features

### Custom Matchers

Extend the framework with custom pattern matchers:

```python
class UnicodePropertyMatcher(Matcher):
    def __init__(self, property_name):
        self.property = property_name
    
    def match(self, stream: TokenStream):
        # Custom Unicode matching logic
        pass
```

### Observable State

Enable state observation for debugging:

```python
indent_stack = State.stack([0], observable=True)

def trace_indents(operation, value, stack):
    print(f"Indent {operation}: {value} -> {stack}")

indent_stack.observe(trace_indents)
```

### Context Managers

Customize lifecycle behavior through context manager extension:

```python
class CustomContext(TokenizationContext):
    def __enter__(self):
        # Additional setup
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Additional cleanup
        return super().__exit__(exc_type, exc_val, exc_tb)
```

## Conclusion

The Lexer Builder Framework provides a production-ready foundation for lexical analysis in Python. Through declarative patterns, typed state management, and automatic lifecycle handling, developers can build sophisticated lexers with minimal boilerplate while maintaining clarity and performance.