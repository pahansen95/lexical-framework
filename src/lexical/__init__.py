"""
# Lexical Analysis Framework

A declarative framework for building lexical analyzers and parsers with integrated
observability. The framework provides a complete pipeline from source text to
syntax trees through composable, pattern-based components.

## Architecture

The framework implements a four-stage processing pipeline:

```
Source Text → Tokenization → Parsing → Tree Building → Transformation
               (Lexer)       (Parser)   (SyntaxTree)    (Visitors)
```

Each stage is designed for both standalone use and pipeline composition,
with observability woven throughout for debugging and analysis.

## Core Components

**Lexer**: Pattern-based tokenization with state management
- Declarative pattern definitions using class attributes
- Support for regex, literal, and method-based patterns
- Built-in state management (counters, stacks, generic state)
- Priority-based pattern matching

**Parser**: Recursive descent parsing with automatic tree building
- Integrated CST construction during parsing
- Parser combinators (choice, many, optional, separated)
- Automatic backtracking with state restoration
- Structural token handling

**SyntaxTree**: Immutable tree representation with lazy navigation
- Frozen immutable nodes for structural sharing
- Lazy view layer for efficient traversal
- Position tracking throughout the tree
- Visitor pattern for transformations

**Observability**: Zero-overhead instrumentation
- Parse stack tracking and timing
- Token emission events
- Tree construction observation
- Null context for production use

## Usage Patterns

### Basic Lexer
```python
from lexical import Lexer, pattern

class MyLexer(Lexer):
    NUMBER = pattern.regex(r'\\d+')
    PLUS = pattern.literal('+')
    WHITESPACE = pattern.regex(r'\\s+', skip=True)

lexer = MyLexer()
tokens = list(lexer.lex("1 + 2"))
```

### Parser with Tree Building
```python
from lexical import Parser, rule

class MyParser(Parser):
    @rule()
    def expression(self):
        self.term()
        while self.match('PLUS'):
            self.consume()
            self.term()

    def term(self):
        self.expect('NUMBER')

parser = MyParser(tokens)
tree = parser.parse()
```

### Tree Transformation
```python
from lexical import TreeVisitor

class Evaluator(TreeVisitor):
    def visit_expression(self, node):
        # Transform expression nodes
        return sum(self.visit(child) for child in node.children)

    def visit_NUMBER(self, node):
        return int(node.text)
```

## Design Principles

- **Declarative**: Define patterns and rules, not parsing algorithms
- **Composable**: Each component works standalone or in pipelines
- **Observable**: Built-in instrumentation with zero overhead when disabled
- **Immutable**: Trees use structural sharing for efficiency
- **Type-Safe**: Full type annotations for static analysis

## Quick Start

For common use cases, import the main components:

```python
from lexical import Lexer, Parser, pattern, rule, SyntaxTree
```

For advanced usage, access specialized components:

```python
from lexical.tokenize import Token, State, Counter
from lexical.tree import TreeVisitor, TreeTransformer
from lexical.observe import LexicalContext
```
"""

# Core tokenization
from .tokenize import (
  Lexer,
  pattern,
  Token,
  LexError,
  State,
  Counter,
  Stack,
  token,  # decorator
)

# Parsing framework
from .parse import (
  Parser,
  ParseError,
  rule,  # decorator
)

# Tree structures
from .tree import (
  SyntaxTree,
  NodeView,
  TreeVisitor,
  TreeTransformer,
  # Frozen types are internal implementation details
)

# Position tracking (consider if these should be public)
from .position import (
  Position,
  PositionRange,
)

# Observability
from .observe import (
  LexicalContext,
)

# Version info
__version__ = "0.1.0"

# Public API
__all__ = [
  # Core classes
  "Lexer",
  "Parser",
  "SyntaxTree",
  # Factories and decorators
  "pattern",
  "rule",
  "token",
  # Data types
  "Token",
  "NodeView",
  "Position",
  "PositionRange",
  # Errors
  "LexError",
  "ParseError",
  # State management
  "State",
  "Counter",
  "Stack",
  # Tree operations
  "TreeVisitor",
  "TreeTransformer",
  # Observability
  "LexicalContext",
]
