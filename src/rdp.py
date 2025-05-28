
"""
Recursive Descent Parser (RDP) Framework

A declarative framework for building recursive descent parsers with automatic
structural token handling and CST construction.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union, Set, Type, Callable, Tuple
from contextlib import contextmanager
import functools

# ===== Core Token Infrastructure =====

@dataclass
class Token:
    """Represents a lexical token with position information."""
    type: str
    value: Any
    line: int
    column: int
    offset: int
    
    def __repr__(self):
        return f"Token({self.type}:{repr(self.value)})"


@dataclass
class Position:
    """Represents a position in the token stream."""
    offset: int


class ParseError(Exception):
    """Raised when parsing fails."""
    pass


class TokenStream:
    """Manages navigation through a sequence of tokens."""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        
    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look ahead at token without consuming."""
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None
        
    def consume(self) -> Token:
        """Consume and return the current token."""
        if self.at_end():
            raise ParseError("Unexpected end of input")
        token = self.tokens[self.pos]
        self.pos += 1
        return token
        
    def match(self, *types: str) -> bool:
        """Check if current token matches any of the given types."""
        token = self.peek()
        return token and token.type in types
        
    def expect(self, *types: str) -> Token:
        """Consume token if it matches expected types, otherwise error."""
        token = self.peek()
        if not token:
            raise ParseError(f"Expected {types} but reached end of input")
        if token.type not in types:
            raise ParseError(f"Expected {types} but got {token.type} at line {token.line}")
        return self.consume()
        
    def checkpoint(self) -> Position:
        """Save current position for potential backtracking."""
        return Position(self.pos)
        
    def restore(self, position: Position):
        """Restore to a previously saved position."""
        self.pos = position.offset
        
    def at_end(self) -> bool:
        """Check if at end of token stream."""
        return self.pos >= len(self.tokens)
        
    def current_pos(self) -> int:
        """Get current position index."""
        return self.pos


# ===== Parse Tree Representation =====

@dataclass
class Node:
    """Represents a node in the Concrete Syntax Tree."""
    type: str
    children: List[Union['Node', Token]] = field(default_factory=list)
    span: Tuple[int, int] = (0, 0)
    
    def accept(self, visitor):
        """Accept a visitor for traversal."""
        method_name = f'visit_{self.type}'
        method = getattr(visitor, method_name, visitor.generic_visit)
        return method(self)
        
    def __repr__(self):
        return f"Node({self.type}, {len(self.children)} children)"


# ===== Structural Rules System =====

class StructuralRules:
    """
    Base class defining which tokens are automatically consumed between
    semantic elements.
    """
    
    # Default token categories
    WHITESPACE = {'WHITESPACE', 'SPACE', 'TAB'}
    LINEBREAK = {'NEWLINE', 'CRLF', 'LF'}
    COMMENT = {'COMMENT', 'LINE_COMMENT', 'BLOCK_COMMENT', 'MULTILINE_COMMENT'}
    
    @classmethod
    def between_tokens(cls) -> Set[str]:
        """Tokens consumed between semantic elements."""
        return cls.WHITESPACE | cls.LINEBREAK | cls.COMMENT
    
    @classmethod
    def line_continuation(cls) -> Set[str]:
        """Tokens that continue logical lines."""
        return cls.WHITESPACE | {'BACKSLASH_NEWLINE'}
    
    @classmethod
    def statement_separator(cls) -> Set[str]:
        """Tokens that separate statements."""
        return cls.LINEBREAK


class NoStructural(StructuralRules):
    """Disable all structural token handling."""
    
    @classmethod
    def between_tokens(cls) -> Set[str]:
        return set()


@dataclass
class StructuralContext:
    """Represents active structural rules configuration."""
    rules: Type[StructuralRules]
    active: bool = True
    capture: bool = True


@dataclass
class RuleContext:
    """Tracks state during rule execution."""
    name: str
    start_pos: int
    children: List[Union[Node, Token]] = field(default_factory=list)
    capture: bool = True
    structural: Optional[Type[StructuralRules]] = None
    
    def add_child(self, child):
        """Add child element if capturing."""
        if self.capture and child is not None:
            self.children.append(child)
            
    def make_node(self, end_pos: int) -> Node:
        """Construct node from captured children."""
        return Node(self.name, self.children, (self.start_pos, end_pos))


# ===== Parser Base Class =====

class Parser:
    """
    Base parser class providing token operations with automatic structural
    handling and parse tree construction.
    """
    
    def __init__(self, 
                 tokens: TokenStream,
                 structural_rules: Type[StructuralRules] = StructuralRules,
                 debug: bool = False):
        self.tokens = tokens
        self.debug = debug
        self.rule_stack: List[RuleContext] = []
        self.structural_stack = [StructuralContext(structural_rules)]
        
        # Semantic token cache for efficient lookahead
        self._next_semantic_pos = None
        self._cached_from_pos = None
    
    @property
    def current_structural(self) -> StructuralContext:
        """Get current structural context."""
        return self.structural_stack[-1]
    
    def _invalidate_cache(self):
        """Invalidate semantic token cache."""
        self._cached_from_pos = None
        self._next_semantic_pos = None
    
    def _debug_log(self, message: str):
        """Log debug message if debug mode enabled."""
        if self.debug:
            indent = "  " * len(self.rule_stack)
            print(f"[DEBUG] {indent}{message}")
    
    def consume(self) -> Token:
        """Consume token with automatic structural handling."""
        self._invalidate_cache()
        
        # Consume structural tokens before
        self._consume_structural()
        
        # Consume semantic token
        token = self.tokens.consume()
        self._capture(token)
        
        if self.debug:
            self._debug_log(f"Consumed {token.type}: {repr(token.value)}")
        
        # Consume structural tokens after
        self._consume_structural()
        
        return token
    
    def expect(self, *types: str) -> Token:
        """Expect token of given types with structural handling."""
        self._invalidate_cache()
        
        # Consume structural tokens before
        self._consume_structural()
        
        # Expect semantic token
        token = self.tokens.expect(*types)
        self._capture(token)
        
        if self.debug:
            self._debug_log(f"Expected {token.type}: {repr(token.value)}")
        
        # Consume structural tokens after
        self._consume_structural()
        
        return token
    
    def match(self, *types: str) -> bool:
        """Match next semantic token, skipping structural tokens."""
        current_pos = self.tokens.current_pos()
        
        # Use cache if valid
        if self._cached_from_pos == current_pos and self._next_semantic_pos is not None:
            self.tokens.pos = self._next_semantic_pos
            result = self.tokens.match(*types)
            self.tokens.pos = current_pos
            
            if self.debug and result:
                token = self.tokens.tokens[self._next_semantic_pos]
                self._debug_log(f"Matched (cached) {token.type}")
            
            return result
        
        # Calculate and cache semantic position
        saved_pos = current_pos
        self._skip_structural()
        self._next_semantic_pos = self.tokens.current_pos()
        self._cached_from_pos = saved_pos
        
        result = self.tokens.match(*types)
        
        if self.debug and result:
            token = self.tokens.peek()
            self._debug_log(f"Matched {token.type}")
        
        self.tokens.pos = saved_pos
        return result
    
    def _skip_structural(self):
        """Skip structural tokens without capturing."""
        if not self.current_structural.active:
            return
            
        structural_types = self.current_structural.rules.between_tokens()
        skipped = 0
        while self.tokens.match(*structural_types):
            self.tokens.consume()
            skipped += 1
        
        if self.debug and skipped > 0:
            self._debug_log(f"Skipped {skipped} structural tokens")
    
    def _consume_structural(self):
        """Consume and capture structural tokens."""
        if not self.current_structural.active:
            return
            
        consumed = []
        structural_types = self.current_structural.rules.between_tokens()
        
        while self.tokens.match(*structural_types):
            token = self.tokens.consume()
            consumed.append(token)
            if self.current_structural.capture:
                self._capture(token)
        
        if self.debug and consumed:
            location = f"in {self.rule_stack[-1].name}" if self.rule_stack else "at top level"
            types = [t.type for t in consumed]
            self._debug_log(f"Consumed structural {location}: {types}")
    
    def _capture(self, item):
        """Add item to current rule context if capturing."""
        if self.rule_stack and self.rule_stack[-1].capture:
            self.rule_stack[-1].add_child(item)
    
    @contextmanager
    def structural_context(self, 
                          rules: Type[StructuralRules],
                          active: bool = True,
                          capture: bool = True):
        """Temporarily change structural handling."""
        self.structural_stack.append(StructuralContext(rules, active, capture))
        self._invalidate_cache()
        try:
            yield
        finally:
            self.structural_stack.pop()
            self._invalidate_cache()
    
    # ===== Parser Combinators =====
    
    def choice(self, *alternatives: Callable) -> Any:
        """Try alternatives in order until one succeeds."""
        checkpoint = self.tokens.checkpoint()
        last_error = None
        
        for i, alt in enumerate(alternatives):
            try:
                if self.debug:
                    self._debug_log(f"Trying alternative {i+1}/{len(alternatives)}")
                return alt()
            except ParseError as e:
                last_error = e
                self.tokens.restore(checkpoint)
                self._invalidate_cache()
                
        raise last_error or ParseError("No alternatives matched")
    
    def repeats(self, 
                parser_fn: Callable, 
                min_count: int = 0, 
                max_count: Optional[int] = None) -> List:
        """
        Parse repeated occurrences within specified bounds.
        
        Args:
            parser_fn: Parser function to repeat
            min_count: Minimum repetitions required (default: 0)
            max_count: Maximum repetitions allowed (default: None/unbounded)
        
        Returns:
            List of parsed results
        """
        results = []
        
        # Parse required minimum occurrences
        for i in range(min_count):
            try:
                results.append(parser_fn())
            except ParseError as e:
                if self.debug:
                    self._debug_log(f"repeats: failed at required occurrence {i+1}/{min_count}")
                raise ParseError(f"Expected at least {min_count} occurrences, got {i}")
        
        # Parse optional occurrences up to maximum
        while max_count is None or len(results) < max_count:
            checkpoint = self.tokens.checkpoint()
            try:
                results.append(parser_fn())
            except ParseError:
                self.tokens.restore(checkpoint)
                self._invalidate_cache()
                break
        
        if self.debug:
            self._debug_log(f"repeats({min_count},{max_count}): collected {len(results)} items")
        
        return results
    
    def many(self, parser_fn: Callable) -> List:
        """Parse zero or more occurrences."""
        return self.repeats(parser_fn, 0, None)
    
    def some(self, parser_fn: Callable) -> List:
        """Parse one or more occurrences."""
        return self.repeats(parser_fn, 1, None)
    
    def optional(self, parser_fn: Callable) -> Optional[Any]:
        """Parse zero or one occurrence."""
        results = self.repeats(parser_fn, 0, 1)
        return results[0] if results else None
    
    def separated(self, parser_fn: Callable, delimiter: str) -> List:
        """Parse delimited sequence."""
        results = []
        results.append(parser_fn())
        while self.match(delimiter):
            self.consume()
            results.append(parser_fn())
        return results
    
    def _execute_rule(self, func, ctx, flatten, *args, **kwargs):
        """Execute a rule function with proper context management."""
        try:
            result = func(self, *args, **kwargs)
            
            if ctx.capture and ctx.children:
                if flatten and len(ctx.children) == 1:
                    node_result = ctx.children[0]
                else:
                    node_result = ctx.make_node(self.tokens.current_pos())
                
                # Add to parent context if exists
                if len(self.rule_stack) > 1:
                    parent_ctx = self.rule_stack[-2]
                    if parent_ctx.capture:
                        parent_ctx.add_child(node_result)
                
                return node_result
            
            elif result is not None and len(self.rule_stack) > 1:
                parent_ctx = self.rule_stack[-2]
                if parent_ctx.capture:
                    parent_ctx.add_child(result)
            
            return result
            
        finally:
            self.rule_stack.pop()


# ===== Rule Decorator =====

def rule(fn: Callable = None,
         *,
         node: Optional[str] = None,
         flatten: bool = False,
         capture: bool = True,
         structural: Optional[Type[StructuralRules]] = None) -> Callable:
    """
    Decorator that transforms a method into a parsing rule.
    
    Args:
        node: Custom node type name (defaults to method name)
        flatten: If True, unwrap single child nodes
        capture: If False, don't capture tokens/nodes
        structural: Custom structural rules for this rule
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            rule_name = node or func.__name__
            
            if self.debug:
                self._debug_log(f"Entering rule: {rule_name}")
            
            ctx = RuleContext(
                rule_name,
                self.tokens.current_pos(),
                capture=capture,
                structural=structural
            )
            self.rule_stack.append(ctx)
            
            # Handle structural override
            if structural is not None:
                with self.structural_context(structural):
                    result = self._execute_rule(func, ctx, flatten, *args, **kwargs)
            else:
                result = self._execute_rule(func, ctx, flatten, *args, **kwargs)
            
            if self.debug:
                self._debug_log(f"Exiting rule: {rule_name}")
            
            return result
                
        wrapper._is_rule = True
        return wrapper
    
    return decorator if fn is None else decorator(fn)


# ===== Visitor Pattern =====

class Visitor:
    """Base class for CST traversal and transformation."""
    
    def visit(self, node: Union[Node, Token]) -> Any:
        """Visit a node or token."""
        if isinstance(node, Token):
            return self.visit_token(node)
        method_name = f'visit_{node.type}'
        method = getattr(self, method_name, self.generic_visit)
        return method(node)
    
    def visit_token(self, token: Token) -> Any:
        """Visit a token node."""
        return token.value
    
    def generic_visit(self, node: Node) -> Any:
        """Default visitor for unhandled node types."""
        for child in node.children:
            if isinstance(child, (Node, Token)):
                self.visit(child)


# ===== Example Usage =====

if __name__ == "__main__":
    # Example: Simple arithmetic expression parser
    
    class ExprParser(Parser):
        @rule
        def expression(self):
            left = self.term()
            while self.match('PLUS', 'MINUS'):
                op = self.consume()
                right = self.term()
                left = Node('binop', [left, op, right])
            return left
        
        @rule
        def term(self):
            left = self.factor()
            while self.match('TIMES', 'DIVIDE'):
                op = self.consume()
                right = self.factor()
                left = Node('binop', [left, op, right])
            return left
        
        @rule(flatten=True)
        def factor(self):
            if self.match('NUMBER'):
                return Node('number', [self.consume()])
            
            if self.match('LPAREN'):
                self.consume()
                expr = self.expression()
                self.expect('RPAREN')
                return expr
            
            raise ParseError("Expected number or parenthesized expression")
    
    # Example tokens
    tokens = [
        Token('NUMBER', 1, 1, 1, 0),
        Token('WHITESPACE', ' ', 1, 2, 1),
        Token('PLUS', '+', 1, 3, 2),
        Token('WHITESPACE', ' ', 1, 4, 3),
        Token('NUMBER', 2, 1, 5, 4),
    ]
    
    # Parse
    stream = TokenStream(tokens)
    parser = ExprParser(stream)
    result = parser.expression()
    
    print(f"Parsed: {result}")