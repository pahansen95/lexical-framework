"""
JSON Parser Example using Current Framework

A complete JSON parser demonstrating the current framework's capabilities including:
- Simplified lexer with declarative patterns
- Clean parser with automatic CST construction
- Visitor pattern for value extraction
"""

import re
from typing import List, Any, Union
from lex import Lexer, Token, pattern, token
from parse import Parser, TokenStream, Node, rule, Visitor, ParseError


# ===== JSON Lexer =====


class JSONLexer(Lexer):
    """Tokenizes JSON input using the simplified lexer framework."""
    
    # Literals
    NULL = pattern.literal("null", priority=10)
    TRUE = pattern.literal("true", priority=10)
    FALSE = pattern.literal("false", priority=10)
    
    # Numbers (using regex pattern)
    NUMBER = pattern.regex(
        r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?",
        priority=5
    )
    
    # Strings (simplified - doesn't handle all escape sequences)
    STRING = pattern.regex(
        r'"(?:[^"\\]|\\.)*"',
        priority=5
    )
    
    # Punctuation
    LBRACE = pattern.literal("{")
    RBRACE = pattern.literal("}")
    LBRACKET = pattern.literal("[")
    RBRACKET = pattern.literal("]")
    COMMA = pattern.literal(",")
    COLON = pattern.literal(":")
    
    # Whitespace (skip)
    WHITESPACE = pattern.regex(r"[ \t\r\n]+", skip=True)


# ===== JSON Parser =====


class JSONParser(Parser):
    """Recursive descent parser for JSON."""
    
    def __init__(self, tokens: List[Token]):
        super().__init__(tokens)
        # Enable structural token handling
        self.skip_structural = True
        self.structural_tokens = {"WHITESPACE"}
    
    @rule
    def json(self):
        """JSON root - any value."""
        return self.value()
    
    def value(self):
        """JSON value - object, array, string, number, or literal."""
        return self.choice(
            self.object,
            self.array, 
            self.string,
            self.number,
            self.literal
        )
    
    @rule
    def object(self):
        """JSON object - { members? }"""
        self.expect("LBRACE")
        
        members = []
        if not self.match("RBRACE"):
            members = self.separated(self.member, "COMMA")
        
        self.expect("RBRACE")
        return members
    
    def member(self):
        """Object member - string : value"""
        key = self.string()
        self.expect("COLON")
        value = self.value()
        return (key, value)
    
    @rule
    def array(self):
        """JSON array - [ elements? ]"""
        self.expect("LBRACKET")
        
        elements = []
        if not self.match("RBRACKET"):
            elements = self.separated(self.value, "COMMA")
        
        self.expect("RBRACKET")
        return elements
    
    def string(self):
        """JSON string literal."""
        token = self.expect("STRING")
        # Remove quotes and handle basic escapes
        content = token.value[1:-1]
        content = content.replace(r'\"', '"')
        content = content.replace(r'\\', '\\')
        content = content.replace(r'\/', '/')
        content = content.replace(r'\b', '\b')
        content = content.replace(r'\f', '\f')
        content = content.replace(r'\n', '\n')
        content = content.replace(r'\r', '\r')
        content = content.replace(r'\t', '\t')
        return content
    
    def number(self):
        """JSON number literal."""
        token = self.expect("NUMBER")
        if "." in token.value or "e" in token.value or "E" in token.value:
            return float(token.value)
        return int(token.value)
    
    def literal(self):
        """JSON literal - null, true, false."""
        if self.match("NULL"):
            self.consume()
            return None
        elif self.match("TRUE"):
            self.consume()
            return True
        elif self.match("FALSE"):
            self.consume()
            return False
        else:
            raise ParseError("Expected literal (null, true, false)")


# ===== JSON Value Extractor =====


class JSONValueExtractor(Visitor):
    """Extract Python values from JSON CST."""
    
    def visit_json(self, node: Node) -> Any:
        """Root node."""
        # The json node contains the value as its child
        if node.children:
            return self.visit(node.children[0])
        return None
    
    def visit_object(self, node: Node) -> dict:
        """Convert to Python dict."""
        result = {}
        
        for child in node.children:
            if isinstance(child, Token):
                continue  # Skip punctuation tokens
            elif isinstance(child, tuple):
                # Direct member tuple
                key, value = child
                result[key] = value
            elif isinstance(child, list):
                # List of members
                for item in child:
                    if isinstance(item, tuple):
                        key, value = item
                        result[key] = value
        
        return result
    
    def visit_array(self, node: Node) -> list:
        """Convert to Python list."""
        result = []
        
        for child in node.children:
            if isinstance(child, Token):
                continue  # Skip punctuation tokens
            elif isinstance(child, list):
                # List of values
                for item in child:
                    if not isinstance(item, Token):
                        result.append(item)
            elif not isinstance(child, Token):
                result.append(child)
        
        return result
    
    def visit_token(self, token: Token) -> Any:
        """Handle tokens."""
        return token.value
    
    def generic_visit(self, node: Node) -> Any:
        """Handle other nodes."""
        # For nodes we don't have specific handlers
        if len(node.children) == 1:
            return self.visit(node.children[0])
        return super().generic_visit(node)


# ===== Convenience Functions =====


def parse_json(text: str) -> Any:
    """Parse JSON text into Python objects."""
    # Tokenize
    lexer = JSONLexer()
    tokens = list(lexer.lex(text))
    
    # Parse to CST  
    parser = JSONParser(tokens)
    cst = parser.json()
    
    # Extract values
    extractor = JSONValueExtractor()
    return extractor.visit(cst)


def parse_json_to_cst(text: str) -> Node:
    """Parse JSON text to CST for inspection."""
    lexer = JSONLexer()
    tokens = list(lexer.lex(text))
    parser = JSONParser(tokens)
    return parser.json()


# ===== Example Usage =====

if __name__ == "__main__":
    import json
    
    # Example 1: Simple object
    obj = {"name": "John Doe", "age": 30, "active": True, "balance": 1234.56}
    json_text = json.dumps(obj)
    
    print("=== Example 1: Simple Object ===")
    print(f"Input: {json_text}")
    result = parse_json(json_text)
    print(f"Parsed: {result}")
    print(f"Match: {result == obj}")
    print()
    
    # Example 2: Nested structures
    obj2 = {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ],
        "count": 2,
        "metadata": {
            "version": "1.0",
            "features": ["auth", "api", "websocket"]
        }
    }
    json_text2 = json.dumps(obj2, indent=2)
    
    print("=== Example 2: Nested Structures ===")
    print(f"Input: {json_text2[:50]}...")
    result2 = parse_json(json_text2)
    print(f"Parsed: {result2}")
    print(f"Match: {result2 == obj2}")
    print()
    
    # Example 3: Array of values
    arr = [1, 2.5, "hello", True, None, {"key": "value"}]
    json_text3 = json.dumps(arr)
    
    print("=== Example 3: Array ===")
    print(f"Input: {json_text3}")
    result3 = parse_json(json_text3)
    print(f"Parsed: {result3}")
    print(f"Match: {result3 == arr}")
    print()
    
    # Example 4: CST inspection
    print("=== Example 4: CST Structure ===")
    simple_obj = {"a": [1, 2, 3]}
    simple_json = json.dumps(simple_obj)
    print(f"Input: {simple_json}")
    cst = parse_json_to_cst(simple_json)
    
    def print_cst(node, indent=0):
        """Pretty print CST structure."""
        prefix = "  " * indent
        if isinstance(node, Token):
            print(f"{prefix}Token({node.type}: {repr(node.value)})")
        elif isinstance(node, tuple):
            print(f"{prefix}Tuple:")
            for item in node:
                if isinstance(item, (str, int, float, bool)) or item is None:
                    print(f"{prefix}  {repr(item)}")
                else:
                    print_cst(item, indent + 1)
        elif isinstance(node, list):
            print(f"{prefix}List[{len(node)}]:")
            for item in node:
                print_cst(item, indent + 1)
        elif isinstance(node, (str, int, float, bool)) or node is None:
            print(f"{prefix}Value: {repr(node)}")
        elif isinstance(node, Node):
            print(f"{prefix}Node({node.type}, {len(node.children)} children)")
            for child in node.children:
                print_cst(child, indent + 1)
        else:
            print(f"{prefix}Unknown: {type(node).__name__} = {repr(node)}")
    
    print_cst(cst)
    
    # Example 5: Error handling
    print("\n=== Example 5: Error Handling ===")
    bad_json = '{"unclosed": '
    try:
        parse_json(bad_json)
    except Exception as e:
        print(f"Error: {e}")
    
    bad_json2 = '{"key": undefined}'
    try:
        parse_json(bad_json2)
    except Exception as e:
        print(f"Error: {e}")