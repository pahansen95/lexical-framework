# Contributor's Guide

> This document describes expectations of developers, provides development frameworks, establishes directives on coding conventions, offers opinionated recommendations on developer environments, and concludes with further reading for contributor success.

## What is Good?

> *“Simplicity is prerequisite for reliability.” — Edsger W. Dijkstra*

Every healthy codebase shares a small set of enduring qualities.  This guide opens with them so that every contributor—from first‑time committer to long‑term maintainer—starts with the same mental model and vocabulary.

### 1 Correctness is non‑negotiable

Our first duty is to ship behaviour that faithfully matches user‑visible intent and internal contracts. Tests, static checks and—where stakes demand—formal proofs are the guard‑rails.  If the behaviour is wrong, nothing else buys redemption.

### 2 Simplicity beats cleverness

We seek the *least* complicated design that solves today’s need while leaving tomorrow unobstructed. Prefer clear data structures and straight‑line logic to intricate abstractions; embrace YAGNI and delete dead paths early.

### 3 Readability enables change

Code is a long‑lived conversation between authors. Names should reveal intent; control flow should read top‑to‑bottom; modules should have single, obvious responsibilities. If an unfamiliar engineer cannot reason about a unit in minutes, refactor or document until they can.

### 4 Fitness for purpose

Quality lives in context: throughput matters in services, determinism in analytics, robustness in safety‑critical paths. Meet the non‑functional constraints that matter—and prove it with measurements, not intuition.

### 5 Sustainable maintainability

Every PR must make the future easier, never harder. We budget time for refactoring, guard against technical debt, and keep build, test and deploy feedback loops fast. A patch that adds value today at the cost of tomorrow’s velocity is not “done”.

---

### How to apply this model in practice

| When you…            | Ask yourself…                                                |
| -------------------- | ------------------------------------------------------------ |
| Design a feature     | *Is the simplest correct design obvious?  What will it look like after three more iterations?* |
| Review code          | *Does this change shrink or grow complexity?  Could I maintain it six months from now?* |
| Optimise performance | *Are we optimising the 3 % of code that matters?  Can we isolate the tricky bits behind a clear façade?* |
| Take a shortcut      | *What debt are we incurring?  When—and how—will we pay it off?* |

**Key expectation:**  *If a contribution erodes any pillar above, it requires a clear, written justification and a plan to restore balance.*

Embodying these principles keeps the codebase pliable, reliable and a pleasure to work with—today and for the next generation of contributors.

---

## How to Develop Good

> *“Process without principles is bureaucracy; principles without process is wishful thinking.” — Mark Schwartz*

To write "good" code all you need to do is:

1. Think First
2. Code Second
3. Continuously Iterate

We establish a simple framework, The **A · I · O loop**, to guide developers: 

* **Articulate** *what* we’re doing and *why* before writing any code.
* **Implement** your vision as models, source code & tests in equal measure.
* **Observe** runtime behavior to understand the gap & iterate accordingly.

Spend roughly equal time articulating & implementing. Automate Observations to quickly iterate.

---

### **A · I · O Loop Procedures**

#### Articulate — *think first*

1. **Discover** – Capture intent; describe your mental models plainly; record user's desired outcomes & expectations of behavior.
2. **Constrain** – Establish (or re-use) a common vernacular; define the extents of your problem space; state your predicates & baseline assumptions.
3. **Architect** – Identify the structure of data & procedural flow of behaviors; understand pre-established patterns and paradigms; posit questions on known unknowns.

Use this process to explore your understanding of the problem & how it maps to your development environment. You are formulating mental models. Spend equal time Articulating as you do Implementing. You're done when you feel like you're hitting diminishing returns (e.g. splitting hairs, chasing rabbits, or talking philosophy).

#### Implement — *code second*

4. **Model** – Write structural & behavioral specifications; formally or otherwise.
5. **Code** – Build a solution that matches your mental models.
6. **Test** – Attempt to falsify behaviors & structures of the code.

Use this process to materialize & validate your mental models. Source code is only one piece of the puzzle. Don't get hung up on premature optimizations or perfection; mark anything that "smells", so we know to come back to it later. Focus on mapping your mental models to executable software. Spend equal time Implementing as you do Articulating. You're done when you feel like you're hitting diminishing returns (e.g. refactoring for style, playing golf or bogged in technical debt).

#### Observe — *continuously iterate*

7. **Measure** – Record & analyze logs, metrics & profiles to determine real world behavior.
8. **Analyze** – Conduct Gap Analysis; compare the observed behavior with your recorded intent.
9. **Iterate** – Measure the error & describe next steps.

Use this process to inform what comes next. Favor automation & fast feedback to increase the time you spend articulating & implementing. If the gap is conceptual, loop to *Articulate*; if it’s execution, loop to *Implement*. Iterate until you have "good" code. If you feel the process isn't working, then challenge your approach. If accrued technical debt is a burden, then pay it down. If there is no gap, then congratulations, you're done... for now.

## Coding Conventions

Based on established patterns in the `lex` and `parse` modules, contributors should follow these conventions to maintain consistency and readability across the codebase.

### Naming Standards

**Classes**: Use PascalCase for all class names. Classes should represent concepts or entities.
```python
class TokenStream:      # ✓ Good
class token_stream:     # ✗ Avoid
```

**Functions and Methods**: Use snake_case for all functions and methods. Names should be verb phrases that describe actions.
```python
def consume_token():    # ✓ Good
def consumeToken():     # ✗ Avoid
```

**Constants**: Use UPPERCASE with underscores for module-level constants. Group related constants together.
```python
WHITESPACE = {"SPACE", "TAB"}     # ✓ Good
LINE_BREAK = {"NEWLINE", "CRLF"}  # ✓ Good
```

**Private Members**: Prefix with single underscore for internal implementation details.
```python
def _consume_structural():   # Internal method
self._cached_position = 0    # Internal state
```

**Module Singletons**: Use Capitalized names for factory instances or singleton objects.
```python
State = StateFactory()   # Factory instance
token = TokenFactory()   # Decorator factory
```

### Type Annotations

Type annotations are mandatory for all function signatures and class attributes. Use the typing module for complex types.

```python
def match(self, *types: str) -> bool:  # ✓ Required
    ...

def process(self, tokens: List[Token]) -> Optional[Node]:  # ✓ Clear types
    ...

## Avoid Any unless absolutely necessary
def parse(self, data: Any) -> Any:  # ⚠️ Use specific types
```

### Documentation Standards

**Module Docstrings**: Begin each module with a concise description of its purpose.
```python
"""
Lexer Builder Framework

A declarative framework for building lexical analyzers with stateful pattern 
recognition and automatic lifecycle management.
"""
```

**Class Docstrings**: Document the class purpose, key attributes, and usage patterns.
```python
class TokenStream:
    """
    Character stream with position tracking for lexical analysis.
    
    Provides efficient character-level access with automatic position
    tracking, lookahead capabilities, and error reporting.
    """
```

**Method Docstrings**: Use imperative mood. Document parameters only when non-obvious.
```python
def consume(self) -> Token:
    """Consume token with automatic structural handling."""
    ...

def separated(self, parser_fn: Callable, delimiter: str) -> List:
    """Parse delimited sequence."""
    ...
```

### Code Organization

**Section Headers**: Use comment blocks to separate major sections within modules.
```python
## ===== Core Token Infrastructure =====

## ===== Pattern Matching System =====

## ===== Parser Combinators =====
```

**Class Member Order**: Organize class members consistently:
1. Class variables and constants
2. `__init__` and initialization methods
3. Properties
4. Public methods (grouped by functionality)
5. Private methods

**Import Organization**: Group imports by category with clear separation.
```python
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .state import BootstrapState
from .platform import Platform

import logging
```

### Error Handling

**Custom Exceptions**: Create domain-specific exceptions with rich context.
```python
class ParseError(Exception):
    """Raised when parsing fails."""
    pass

class LexError(Exception):
    """Enhanced exception for lexical analysis errors with position tracking."""
    def __init__(self, message: str, position: Optional[Position] = None):
        ...
```

**Error Messages**: Provide actionable, context-rich error messages.
```python
## ✓ Good - provides context and location
raise ParseError(f"Expected {types} but got {token.type} at line {token.line}")

## ✗ Avoid - too generic
raise ParseError("Invalid token")
```

### Design Patterns

**Dataclasses**: Use dataclasses for pure data structures with minimal behavior.
```python
@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int
```

**Context Managers**: Use context managers for resource lifecycle and state management.
```python
@contextmanager
def structural_context(self, rules: Type[StructuralRules]):
    """Temporarily change structural handling."""
    self.structural_stack.append(rules)
    try:
        yield
    finally:
        self.structural_stack.pop()
```

**Decorators**: Use decorators for cross-cutting concerns and declarative syntax.
```python
@rule(node="expression", flatten=True)
def parse_expression(self):
    ...
```

### Performance Considerations

**Caching**: Cache expensive computations with clear invalidation logic.
```python
## Cache semantic position for efficient lookahead
if self._cached_from_pos == current_pos:
    return self._cached_result
```

**Early Returns**: Use guard clauses to reduce nesting and improve readability.
```python
def match(self, text: str) -> bool:
    if self.at_end():
        return False
    
    if not text:
        return True
    
    # Main logic here
```

### Writing Tests

**Test Organization**: Mirror source structure in test directory. Use descriptive test names.
```python
def test_verify_tool_python():     # ✓ Describes what is tested
def test_1():                      # ✗ Non-descriptive
```

**Assertions**: Use specific assertions with clear failure messages.
```python
assert res["installed"], "Python should be installed"  # ✓ Good
assert res["installed"]  # ⚠️ Less helpful on failure
```

### General Guidelines

1. **Prefer Composition**: Build complex behavior from simple, composable parts
2. **Fail Fast**: Validate inputs early and raise clear exceptions
3. **Minimize State**: Prefer functional approaches where practical
4. **Document Intent**: Use names and comments to explain "why", not just "what"
5. **Consistent Abstraction**: Keep abstraction levels consistent within a function

These conventions ensure the codebase remains maintainable, readable, and consistent as it evolves.

## Environment & Tooling

> Fill in as necessary

## Further Reading

> Fill in as necessary