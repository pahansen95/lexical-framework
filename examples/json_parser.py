"""
JSON Parser using Frozen Tree Framework

Demonstrates parsing JSON into immutable syntax trees with automatic
CST construction and value extraction through visitors.
"""

from typing import Any, Dict, List
from lex import Lexer, pattern
from parse import Parser, rule, Visitor, ParseError
from tree import SyntaxTree, NodeView


# ===== JSON Lexer =====


class JSONLexer(Lexer):
  """Tokenizes JSON input"""

  # Literals
  NULL = pattern.literal("null", priority=10)
  TRUE = pattern.literal("true", priority=10)
  FALSE = pattern.literal("false", priority=10)

  # Numbers (simplified - doesn't handle all edge cases)
  NUMBER = pattern.regex(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", priority=5)

  # Strings (basic escape handling)
  STRING = pattern.regex(r'"(?:[^"\\]|\\.)*"', priority=5)

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
  """Parses JSON into frozen syntax trees"""

  def __init__(self, tokens):
    super().__init__(tokens)
    # JSON doesn't need structural token handling
    self.skip_structural = True

  @rule
  def json(self):
    """JSON root - any value"""
    self.value()

  def value(self):
    """JSON value - object, array, string, number, or literal"""
    self.choice(self.object, self.array, self.string, self.number, self.literal)

  @rule
  def object(self):
    """JSON object - { members? }"""
    self.expect("LBRACE")

    if not self.match("RBRACE"):
      self.separated(self.member, "COMMA")

    self.expect("RBRACE")

  @rule
  def member(self):
    """Object member - string : value"""
    self.string()
    self.expect("COLON")
    self.value()

  @rule
  def array(self):
    """JSON array - [ elements? ]"""
    self.expect("LBRACKET")

    if not self.match("RBRACKET"):
      self.separated(self.value, "COMMA")

    self.expect("RBRACKET")

  def string(self):
    """String literal"""
    self.expect("STRING")

  def number(self):
    """Number literal"""
    self.expect("NUMBER")

  def literal(self):
    """true/false/null"""
    if self.match("TRUE", "FALSE", "NULL"):
      self.consume()
    else:
      raise ParseError("Expected literal (true, false, null)")

  def parse_root(self):
    """Parse JSON grammar root"""
    self.json()


# ===== JSON Value Extractor =====


class JSONValueExtractor(Visitor):
  """Extract Python values from JSON syntax tree"""

  def visit_json(self, node: NodeView) -> Any:
    """Root node contains the value"""
    # JSON node has one child - the value
    return self.visit(node.children[0])

  def visit_object(self, node: NodeView) -> Dict[str, Any]:
    """Convert to Python dict"""
    result = {}

    # Object contains: LBRACE, members..., RBRACE
    for child in node.children:
      if child.kind == "member":
        key, value = self.visit_member(child)
        result[key] = value

    return result

  def visit_member(self, node: NodeView) -> tuple:
    """Extract key-value pair"""
    # Member contains: STRING, COLON, value
    key_token = node.children[0]
    value_node = node.children[2]

    # Remove quotes from string
    key = key_token.text[1:-1]
    key = self._unescape_string(key)

    # Get value
    value = self.visit(value_node)

    return key, value

  def visit_array(self, node: NodeView) -> List[Any]:
    """Convert to Python list"""
    result = []

    # Array contains: LBRACKET, values..., RBRACKET
    for child in node.children:
      if child.kind not in ("LBRACKET", "RBRACKET", "COMMA"):
        result.append(self.visit(child))

    return result

  def visit_STRING(self, node: NodeView) -> str:
    """Extract string value"""
    # Remove quotes and unescape
    text = node.text[1:-1]
    return self._unescape_string(text)

  def visit_NUMBER(self, node: NodeView) -> float:
    """Extract number value"""
    if "." in node.text or "e" in node.text or "E" in node.text:
      return float(node.text)
    return int(node.text)

  def visit_TRUE(self, node: NodeView) -> bool:
    return True

  def visit_FALSE(self, node: NodeView) -> bool:
    return False

  def visit_NULL(self, node: NodeView) -> None:
    return None

  def generic_visit(self, node: NodeView) -> Any:
    """For nodes we don't handle, visit first non-structural child"""
    for child in node.children:
      if child.kind not in ("COMMA", "COLON"):
        return self.visit(child)
    return None

  def _unescape_string(self, text: str) -> str:
    """Handle basic escape sequences"""
    return (
      text.replace(r"\"", '"')
      .replace(r"\\", "\\")
      .replace(r"\/", "/")
      .replace(r"\b", "\b")
      .replace(r"\f", "\f")
      .replace(r"\n", "\n")
      .replace(r"\r", "\r")
      .replace(r"\t", "\t")
    )


# ===== Convenience Functions =====


def parse_json(text: str) -> Any:
  """Parse JSON text into Python objects"""
  # Tokenize
  lexer = JSONLexer()
  tokens = list(lexer.lex(text))

  # Parse to syntax tree
  parser = JSONParser(tokens)
  tree = parser.parse()

  # Extract values
  extractor = JSONValueExtractor()
  return extractor.visit(tree.root)


def parse_json_tree(text: str) -> SyntaxTree:
  """Parse JSON text to syntax tree for inspection"""
  lexer = JSONLexer()
  tokens = list(lexer.lex(text))
  parser = JSONParser(tokens)
  return parser.parse()


# ===== Example Usage =====

if __name__ == "__main__":
  import json

  # Example 1: Simple object
  test1 = '{"name": "John", "age": 30, "active": true}'

  print("=== Example 1: Simple Object ===")
  print(f"Input: {test1}")
  result1 = parse_json(test1)
  print(f"Parsed: {result1}")
  print(f"Match: {result1 == json.loads(test1)}")
  print()

  # Example 2: Nested structures
  test2 = """
    {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ],
        "count": 2,
        "metadata": {
            "version": "1.0",
            "features": ["auth", "api"]
        }
    }
    """

  print("=== Example 2: Nested Structures ===")
  result2 = parse_json(test2)
  print(f"Parsed: {json.dumps(result2, indent=2)}")
  print(f"Match: {result2 == json.loads(test2)}")
  print()

  # Example 3: Inspect syntax tree
  test3 = '{"a": [1, 2, 3]}'

  print("=== Example 3: Syntax Tree ===")
  print(f"Input: {test3}")
  tree = parse_json_tree(test3)
  print("Tree structure:")
  print(tree.dump())
  print()

  # Example 4: Tree navigation
  print("=== Example 4: Tree Navigation ===")
  # Find all numbers in the tree
  numbers = tree.find_all("NUMBER")
  print(f"Found {len(numbers)} numbers:")
  for num in numbers:
    print(f"  {num.text} at position {num.position}")

  # Find the array node
  arrays = tree.find_all("array")
  if arrays:
    array_node = arrays[0]
    print(f"\nArray has {len(array_node.children)} children:")
    for child in array_node.children:
      print(f"  {child.kind}: {child.text or 'node'}")
