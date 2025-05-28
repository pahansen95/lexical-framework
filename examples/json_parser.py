"""
JSON Parser Example using RDP Framework

A complete JSON parser demonstrating the RDP framework's capabilities including:
- Automatic structural token handling (whitespace)
- CST construction
- Clean grammar expression through decorators
"""

import re
from typing import List, Any
from rdp import Token, TokenStream, Parser, StructuralRules, rule, ParseError


# ===== JSON Tokenizer =====


class JSONLexer:
  """Tokenizes JSON input into a stream of tokens."""

  TOKEN_PATTERNS = [
    # Literals
    ("NULL", r"null"),
    ("TRUE", r"true"),
    ("FALSE", r"false"),
    # Numbers
    ("NUMBER", r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?"),
    # Strings (simplified - doesn't handle all escape sequences)
    ("STRING", r'"(?:[^"\\]|\\.)*"'),
    # Punctuation
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("COMMA", r","),
    ("COLON", r":"),
    # Structural
    ("WHITESPACE", r"[ \t\r\n]+"),
  ]

  def __init__(self):
    # Compile patterns
    self.token_re = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_PATTERNS))

  def tokenize(self, text: str) -> List[Token]:
    """Convert text into tokens."""
    tokens = []
    line = 1
    column = 1
    offset = 0

    for match in self.token_re.finditer(text):
      token_type = match.lastgroup
      value = match.group()

      # Create token
      tokens.append(Token(type=token_type, value=value, line=line, column=column, offset=offset))

      # Update position tracking
      offset = match.end()
      if "\n" in value:
        line += value.count("\n")
        column = len(value.split("\n")[-1]) + 1
      else:
        column += len(value)

    # Check for unmatched characters
    if offset < len(text):
      raise ValueError(f"Invalid character at position {offset}: {text[offset]}")

    return tokens


# ===== JSON Structural Rules =====


class JSONStructural(StructuralRules):
  """JSON only needs whitespace handling between tokens."""

  @classmethod
  def between_tokens(cls):
    return {"WHITESPACE"}


# ===== JSON Parser =====


class JSONParser(Parser):
  """Recursive descent parser for JSON."""

  def __init__(self, tokens: TokenStream, debug: bool = False):
    super().__init__(tokens, JSONStructural, debug)

  @rule
  def json(self):
    """JSON root - any value."""
    return self.value()

  @rule
  def value(self):
    """JSON value - object, array, string, number, or literal."""
    return self.choice(self.object, self.array, self.string, self.number, self.literal)

  @rule
  def object(self):
    """JSON object - { members? }"""
    self.expect("LBRACE")

    members = []
    if not self.match("RBRACE"):
      members = self.separated(self.member, "COMMA")

    self.expect("RBRACE")
    return members

  @rule
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

  @rule(capture=False)
  def string(self):
    """JSON string literal."""
    token = self.expect("STRING")
    # Remove quotes and handle basic escapes
    content = token.value[1:-1]
    content = content.replace(r"\"", '"')
    content = content.replace(r"\\", "\\")
    content = content.replace(r"\/", "/")
    content = content.replace(r"\b", "\b")
    content = content.replace(r"\f", "\f")
    content = content.replace(r"\n", "\n")
    content = content.replace(r"\r", "\r")
    content = content.replace(r"\t", "\t")
    return content

  @rule(capture=False)
  def number(self):
    """JSON number literal."""
    token = self.expect("NUMBER")
    if "." in token.value or "e" in token.value or "E" in token.value:
      return float(token.value)
    return int(token.value)

  @rule(capture=False)
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

from rdp import Visitor


class JSONValueExtractor(Visitor):
  """Extract Python values from JSON CST."""

  def visit_json(self, node):
    """Root node."""
    return self.visit(node.children[0])

  def visit_value(self, node):
    """Value wrapper."""
    # Value node contains one child which is the actual value node
    child = node.children[0]
    if hasattr(child, "type"):
      return self.visit(child)
    else:
      # Direct literal value (string, number, bool, None)
      return child

  def visit_object(self, node):
    """Convert to Python dict."""
    result = {}
    for child in node.children:
      if isinstance(child, Token):
        continue  # Skip punctuation tokens
      elif isinstance(child, tuple):
        # Member returns a tuple (key, value)
        key, value = child
        result[key] = value
      elif hasattr(child, "type") and child.type == "member":
        # Visit member nodes
        key, value = self.visit(child)
        result[key] = value
    return result

  def visit_array(self, node):
    """Convert to Python list."""
    result = []
    for child in node.children:
      if isinstance(child, Token):
        continue  # Skip punctuation tokens
      elif hasattr(child, "type") and child.type == "value":
        result.append(self.visit(child))
    return result

  def visit_member(self, node):
    """Extract key-value pair."""
    # Member node should have a tuple as its return value
    if node.children and isinstance(node.children[0], tuple):
      return node.children[0]

    # Otherwise parse the children
    key = None
    value = None
    for child in node.children:
      if isinstance(child, str):
        if key is None:
          key = child
      elif isinstance(child, tuple) and len(child) == 2:
        return child
      elif hasattr(child, "type") and child.type == "value":
        value = self.visit(child)
      elif isinstance(child, (int, float, bool)) or child is None:
        value = child
    return (key, value)

  def generic_visit(self, node):
    """Handle other nodes."""
    # For nodes we don't have specific handlers for
    if len(node.children) == 1 and not hasattr(node.children[0], "type"):
      return node.children[0]
    return super().generic_visit(node)


# ===== Convenience Functions =====


def parse_json(text: str, debug: bool = False) -> Any:
  """Parse JSON text into Python objects."""
  lexer = JSONLexer()
  tokens = lexer.tokenize(text)
  stream = TokenStream(tokens)
  parser = JSONParser(stream, debug=debug)

  # Parse to CST
  cst = parser.json()

  # Extract values
  extractor = JSONValueExtractor()
  return extractor.visit(cst)


def parse_json_to_cst(text: str, debug: bool = False):
  """Parse JSON text to CST for inspection."""
  lexer = JSONLexer()
  tokens = lexer.tokenize(text)
  stream = TokenStream(tokens)
  parser = JSONParser(stream, debug=debug)
  return parser.json()


# ===== Example Usage =====

if __name__ == "__main__":
  import _setup_examples  # noqa: F401
  import json

  # Example 1: Simple object
  obj = {"name": "John Doe", "age": 30, "active": True, "balance": 1234.56}
  json_text = json.dumps(obj)

  print("=== Example 1: Simple Object ===")
  result = parse_json(json_text)
  print(f"Parsed: {result}")
  print()

  # Example 2: Nested structures
  obj2 = {
    "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    "count": 2,
    "metadata": {"version": "1.0", "features": ["auth", "api", "websocket"]},
  }
  json_text2 = json.dumps(obj2, indent=2)

  print("=== Example 2: Nested Structures ===")
  result2 = parse_json(json_text2)
  print(f"Parsed: {result2}")
  print()

  # Example 3: Debug mode to see parsing process
  simple_obj = {"key": "value"}
  simple_json = json.dumps(simple_obj)

  print("=== Example 3: Debug Mode ===")
  print(f"Parsing: {simple_json}")
  result3 = parse_json(simple_json, debug=True)
  print(f"Result: {result3}")
  print()

  # Example 4: CST inspection
  print("=== Example 4: CST Structure ===")
  cst_obj = {"a": [1, 2, 3]}
  cst_json = json.dumps(cst_obj)
  cst = parse_json_to_cst(cst_json)

  def print_cst(node, indent=0):
    """Pretty print CST structure."""
    prefix = "  " * indent
    if isinstance(node, Token):
      print(f"{prefix}Token({node.type}: {repr(node.value)})")
    elif isinstance(node, tuple):
      print(f"{prefix}Tuple:")
      for item in node:
        print_cst(item, indent + 1)
    elif isinstance(node, (str, int, float, bool)) or node is None:
      print(f"{prefix}Literal: {repr(node)}")
    elif hasattr(node, "type"):
      print(f"{prefix}Node({node.type})")
      for child in node.children:
        print_cst(child, indent + 1)
    else:
      print(f"{prefix}Unknown: {repr(node)}")

  print_cst(cst)
