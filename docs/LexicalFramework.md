# Lexical Framework Documentation

## Overview

The Lexical Framework provides a declarative, pattern-based approach to building lexical analyzers and parsers in Python. It simplifies the creation of language processing tools through automatic pattern collection, state management, and CST (Concrete Syntax Tree) construction.

The framework consists of two main components:
- **Lexer Framework** (`lex.py`): Tokenizes input text using declarative pattern definitions
- **Parser Framework** (`parse.py`): Builds recursive descent parsers with automatic CST generation

## Core Concepts

### Lexical Analysis

The lexer transforms raw text into a stream of tokens through pattern matching. Each token represents a meaningful unit in the language being processed.

Key characteristics:
- Declarative pattern definition using class attributes
- Priority-based pattern matching
- Automatic position tracking with line and column information
- Support for stateful lexing with conditional patterns

### Parsing

The parser consumes tokens to build a structured representation of the input. It provides parser combinators and automatic CST construction through decorators.

Key characteristics:
- Recursive descent parsing with backtracking
- Automatic CST node creation via decorators
- Built-in parser combinators (choice, many, optional, etc.)
- Visitor pattern for tree traversal and transformation

## Lexer Framework

### Basic Usage

```python
from lex import Lexer, pattern

class MyLexer(Lexer):
    # Define patterns as class attributes
    NUMBER = pattern.regex(r"\d+", priority=5)
    PLUS = pattern.literal("+")
    MINUS = pattern.literal("-")
    WHITESPACE = pattern.regex(r"\s+", skip=True)

# Use the lexer
lexer = MyLexer()
tokens = list(lexer.lex("123 + 456"))
```

### Pattern Types

#### Regex Patterns
Match text using regular expressions:
```python
IDENTIFIER = pattern.regex(r"[a-zA-Z_]\w*")
NUMBER = pattern.regex(r"\d+(\.\d+)?")
```

#### Literal Patterns
Match exact text sequences:
```python
LPAREN = pattern.literal("(")
KEYWORD_IF = pattern.literal("if", priority=10)
```

#### Method Patterns
Custom matching logic using decorated methods:
```python
@token(priority=5)
def BLOCK_COMMENT(self, pos):
    if pos.match_literal("/*"):
        pos.advance(2)
        while not pos.at_end:
            if pos.match_literal("*/"):
                pos.advance(2)
                return True
            pos.advance()
    return False
```

### Pattern Attributes

- **priority**: Higher values match first (default: 0)
- **skip**: Token is consumed but not yielded (default: False)
- **when**: Conditional function for state-dependent matching
- **at_line_start**: Only matches at the beginning of a line

### State Management

The framework provides built-in state types for managing lexer context:

```python
class StatefulLexer(Lexer):
    # Counter for numeric state
    indent_level = Counter(0)
    
    # Stack for nested contexts
    context_stack = Stack()
    
    # Generic state container
    mode = State("normal")
    
    # Use state in patterns
    STRING = pattern.literal('"', when=lambda self: self.mode.value == "string")
```

### Error Handling

The lexer provides detailed error information with position context:

```python
try:
    tokens = list(lexer.lex(input_text))
except LexError as e:
    print(f"Lexical error at line {e.line}, column {e.column}")
    # Error includes visual indication of position
```

## Parser Framework

### Basic Usage

```python
from parse import Parser, rule

class MyParser(Parser):
    @rule
    def expression(self):
        """Parse an expression."""
        left = self.term()
        while self.match("PLUS", "MINUS"):
            op = self.consume()
            right = self.term()
            left = (op.type, left, right)
        return left
    
    def term(self):
        """Parse a term."""
        return self.expect("NUMBER")
```

### Rule Decorator

The `@rule` decorator automatically creates CST nodes:

```python
@rule
def statement(self):
    # All consumed tokens become children of a 'statement' node
    self.expect("IF")
    self.expression()
    self.expect("THEN")
    self.statement()
```

Customize node creation:
```python
@rule(name="custom_node", capture=False)
def helper_method(self):
    # name: Custom node type
    # capture: Disable automatic node creation
```

### Parser Combinators

#### choice
Try multiple alternatives:
```python
def value(self):
    return self.choice(
        self.number,
        self.string,
        self.boolean
    )
```

#### many / some
Parse repeated occurrences:
```python
statements = self.many(self.statement)    # Zero or more
arguments = self.some(self.expression)    # One or more
```

#### optional
Parse zero or one occurrence:
```python
else_clause = self.optional(self.else_statement)
```

#### separated
Parse delimited sequences:
```python
params = self.separated(self.parameter, "COMMA")
```

### Structural Token Handling

Control how whitespace and comments are processed:

```python
class MyParser(Parser):
    def __init__(self, tokens):
        super().__init__(tokens)
        self.skip_structural = True
        self.structural_tokens = {"WHITESPACE", "COMMENT"}
```

Use context managers for temporary changes:
```python
with self.structural_handling(enabled=False):
    # Whitespace is significant here
    self.parse_indentation()
```

### Visitor Pattern

Transform CST nodes using the visitor pattern:

```python
class Evaluator(Visitor):
    def visit_expression(self, node):
        # Custom handling for expression nodes
        if len(node.children) == 3:
            left = self.visit(node.children[0])
            op = node.children[1].type
            right = self.visit(node.children[2])
            return self.evaluate_op(op, left, right)
    
    def visit_token(self, token):
        # Handle terminal tokens
        if token.type == "NUMBER":
            return int(token.value)
        return token.value
```

## Complete Example

Here's a simple calculator implementation:

```python
# Lexer definition
class CalcLexer(Lexer):
    NUMBER = pattern.regex(r"\d+(\.\d+)?", priority=5)
    PLUS = pattern.literal("+")
    MINUS = pattern.literal("-")
    TIMES = pattern.literal("*")
    DIVIDE = pattern.literal("/")
    LPAREN = pattern.literal("(")
    RPAREN = pattern.literal(")")
    WHITESPACE = pattern.regex(r"\s+", skip=True)

# Parser definition
class CalcParser(Parser):
    def __init__(self, tokens):
        super().__init__(tokens)
        self.skip_structural = True
    
    @rule
    def expression(self):
        left = self.term()
        while self.match("PLUS", "MINUS"):
            op = self.consume()
            right = self.term()
            left = ("binop", op.type, left, right)
        return left
    
    @rule
    def term(self):
        left = self.factor()
        while self.match("TIMES", "DIVIDE"):
            op = self.consume()
            right = self.factor()
            left = ("binop", op.type, left, right)
        return left
    
    def factor(self):
        if self.match("NUMBER"):
            return float(self.consume().value)
        elif self.match("LPAREN"):
            self.consume()
            expr = self.expression()
            self.expect("RPAREN")
            return expr
        else:
            raise ParseError("Expected number or '('")

# Evaluator
class CalcEvaluator(Visitor):
    def visit(self, node):
        if isinstance(node, tuple) and node[0] == "binop":
            op = node[1]
            left = self.visit(node[2])
            right = self.visit(node[3])
            if op == "PLUS": return left + right
            elif op == "MINUS": return left - right
            elif op == "TIMES": return left * right
            elif op == "DIVIDE": return left / right
        elif isinstance(node, (int, float)):
            return node
        return super().visit(node)

# Usage
def calculate(expression):
    lexer = CalcLexer()
    tokens = list(lexer.lex(expression))
    parser = CalcParser(tokens)
    ast = parser.expression()
    evaluator = CalcEvaluator()
    return evaluator.visit(ast)

result = calculate("2 + 3 * 4")  # Returns 14.0
```

## Design Patterns

### Pattern Organization
- Group related patterns together with comments
- Use priority to resolve ambiguities (keywords vs identifiers)
- Mark structural tokens clearly with skip=True

### State Management
- Use Counter for numeric states (indentation, nesting depth)
- Use Stack for context tracking (string literals, comments)
- Use State for mode switching (normal, string, comment modes)

### Parser Structure
- Keep parsing methods focused and single-purpose
- Use combinators to express grammar rules clearly
- Separate syntactic analysis from semantic processing

### Error Recovery
- Provide meaningful error messages with position information
- Use backtracking sparingly to maintain performance
- Consider synchronization points for error recovery

### CST vs AST
- CST preserves all syntactic information (including whitespace)
- Transform CST to AST using the visitor pattern
- Keep transformation logic separate from parsing logic

## Performance Considerations

### Lexer Optimization
- Order patterns by frequency when priorities are equal
- Use anchored regex patterns where possible
- Minimize backtracking in method patterns

### Parser Optimization
- Avoid deep recursion in grammar rules
- Use iteration instead of recursion for repetitive structures
- Cache position markers to reduce allocation overhead

### Memory Usage
- Stream tokens instead of collecting all at once for large inputs
- Consider pruning CST nodes during construction if not needed
- Implement lazy evaluation in visitors when appropriate

## Common Pitfalls

### Pattern Conflicts
- Keywords matching as identifiers: Use higher priority for keywords
- Overlapping patterns: Order matters when priorities are equal
- Greedy regex consumption: Use non-greedy quantifiers when needed

### State Synchronization
- Forgetting to reset state between inputs
- State leaking between lexer instances
- Incorrect state updates in method patterns

### Parser Ambiguity
- Left recursion causing infinite loops
- Ambiguous grammar requiring excessive backtracking
- Missing base cases in recursive rules

### Error Handling
- Not preserving position information through transformations
- Inadequate error context for debugging
- Silent failures in visitor methods