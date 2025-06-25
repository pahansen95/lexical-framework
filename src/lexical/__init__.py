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
"""

# Core tokenization exports
from .tokenize import (
  # Main classes
  Lexer,
  Token,
  Pattern,
  Match,
  LexError,
  # Pattern factory
  pattern,
  # State management
  State,
  Counter,
  Stack,
  StateValue,
  # Decorator
  token,
)

# Parsing framework exports
from .parse import (
  # Main classes
  Parser,
  ParseError,
  TokenStream,
  # Internal types (for advanced usage)
  BuildFrame,
  ParseState,
  # Decorator
  rule,
)

# Tree structure exports
from .tree import (
  # Main classes
  SyntaxTree,
  NodeView,
  TreeVisitor,
  TreeTransformer,
  # Frozen types (implementation but public)
  FrozenNode,
  FrozenToken,
  FrozenElement,
)

# Position tracking exports
from .position import (
  Position,
  PositionRange,
  SourceNavigator,
)

# Observability exports
from .observe import (
  # Context classes
  LexicalContext,
  NullLexicalContext,
  # Event constants
  LEX_TOKEN_EMIT,
  LEX_STATE_TRANSITION,
  LEX_BUFFER_OPERATION,
  LEX_ERROR_RECOVERY,
  PARSE_RULE_ENTER,
  PARSE_RULE_EXIT,
  PARSE_BACKTRACK,
  PARSE_CACHE_HIT,
  PARSE_CACHE_MISS,
  AST_NODE_CREATE,
  AST_TRANSFORM_APPLY,
  AST_VALIDATION_CHECK,
)

# Version info
__version__ = "0.1.0"

# Comprehensive public API
__all__ = [
  # === Tokenization ===
  # Core classes
  "Lexer",
  "Token",
  "Pattern",
  "Match",
  "LexError",
  # Pattern factory
  "pattern",
  # State management
  "State",
  "Counter",
  "Stack",
  "StateValue",
  # Decorators
  "token",
  # === Parsing ===
  # Core classes
  "Parser",
  "ParseError",
  "TokenStream",
  # Internal types
  "BuildFrame",
  "ParseState",
  # Decorators
  "rule",
  # === Tree Structures ===
  # Core classes
  "SyntaxTree",
  "NodeView",
  "TreeVisitor",
  "TreeTransformer",
  # Frozen types
  "FrozenNode",
  "FrozenToken",
  "FrozenElement",
  # === Position Tracking ===
  "Position",
  "PositionRange",
  "SourceNavigator",
  # === Observability ===
  # Contexts
  "LexicalContext",
  "NullLexicalContext",
  # Event constants
  "LEX_TOKEN_EMIT",
  "LEX_STATE_TRANSITION",
  "LEX_BUFFER_OPERATION",
  "LEX_ERROR_RECOVERY",
  "PARSE_RULE_ENTER",
  "PARSE_RULE_EXIT",
  "PARSE_BACKTRACK",
  "PARSE_CACHE_HIT",
  "PARSE_CACHE_MISS",
  "AST_NODE_CREATE",
  "AST_TRANSFORM_APPLY",
  "AST_VALIDATION_CHECK",
]
