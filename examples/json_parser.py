"""
JSON Parser Implementation

A complete JSON parser demonstrating the lexical framework's capabilities
through four distinct phases: tokenization, CST construction, AST generation,
and Python object building.
"""

from typing import Any, Dict, List, Union, Optional
from dataclasses import dataclass
import argparse
import sys
import json

from lexical.tokenize import Lexer, pattern
from lexical.parse import Parser, rule, ParseError
from lexical.tree import SyntaxTree, NodeView, TreeVisitor
from lexical.observe import LexicalContext
from observability import SharedContext, ObservabilityConfig
from observability.handlers import PrintHandler


# ===== Phase 1: Tokenization =====


class JSONLexer(Lexer):
  """
  Tokenizes JSON input into a stream of typed tokens.

  The lexer recognizes JSON's grammatical elements: literals (null, true, false),
  numbers, strings, and structural punctuation. Whitespace is automatically
  skipped to produce a clean token stream.
  """

  # Literal tokens with high priority to avoid identifier conflicts
  NULL = pattern.literal("null", priority=10)
  TRUE = pattern.literal("true", priority=10)
  FALSE = pattern.literal("false", priority=10)

  # Number pattern: optional minus, digits, optional decimal, optional exponent
  NUMBER = pattern.regex(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", priority=5)

  # String pattern: quoted text with basic escape sequences
  STRING = pattern.regex(r'"(?:[^"\\]|\\.)*"', priority=5)

  # Structural tokens
  LBRACE = pattern.literal("{")
  RBRACE = pattern.literal("}")
  LBRACKET = pattern.literal("[")
  RBRACKET = pattern.literal("]")
  COMMA = pattern.literal(",")
  COLON = pattern.literal(":")

  # Skip whitespace automatically
  WHITESPACE = pattern.regex(r"[ \t\r\n]+", skip=True)


# ===== Phase 2: CST Construction =====


class JSONParser(Parser):
  """
  Parses JSON tokens into a Concrete Syntax Tree.

  The CST preserves all syntactic structure, including punctuation,
  enabling accurate source reconstruction and detailed analysis.
  """

  def __init__(self, tokens, obs_context: Optional[LexicalContext] = None):
    super().__init__(tokens, obs_context)
    # JSON doesn't need structural token handling
    self.skip_structural = True

  def parse_root(self):
    """Entry point: JSON document is a single value."""
    self.value()

  @rule()
  def value(self):
    """JSON value: object, array, or primitive."""
    self.choice(self.object, self.array, self.string, self.number, self.boolean, self.null)

  @rule()
  def object(self):
    """Object: { member, member, ... }"""
    self.expect("LBRACE")

    if not self.match("RBRACE"):
      self.separated(self.member, "COMMA")

    self.expect("RBRACE")

  @rule()
  def member(self):
    """Object member: string : value"""
    self.string()
    self.expect("COLON")
    self.value()

  @rule()
  def array(self):
    """Array: [ value, value, ... ]"""
    self.expect("LBRACKET")

    if not self.match("RBRACKET"):
      self.separated(self.value, "COMMA")

    self.expect("RBRACKET")

  def string(self):
    """String literal token."""
    self.expect("STRING")

  def number(self):
    """Number literal token."""
    self.expect("NUMBER")

  def boolean(self):
    """Boolean literal: true or false."""
    if self.match("TRUE", "FALSE"):
      self.consume()
    else:
      raise ParseError("Expected boolean literal")

  def null(self):
    """Null literal."""
    self.expect("NULL")


# ===== Phase 3: AST Generation =====


@dataclass
class JSONValue:
  """Base class for JSON AST nodes."""

  pass


@dataclass
class JSONObject(JSONValue):
  """Object with key-value pairs."""

  members: Dict[str, JSONValue]


@dataclass
class JSONArray(JSONValue):
  """Array of values."""

  elements: List[JSONValue]


@dataclass
class JSONString(JSONValue):
  """String value."""

  value: str


@dataclass
class JSONNumber(JSONValue):
  """Numeric value."""

  value: Union[int, float]


@dataclass
class JSONBoolean(JSONValue):
  """Boolean value."""

  value: bool


@dataclass
class JSONNull(JSONValue):
  """Null value."""

  pass


class JSONASTBuilder(TreeVisitor[JSONValue]):
  """
  Transforms CST into a simplified AST.

  The AST removes syntactic noise (punctuation, whitespace) and creates
  semantic nodes representing JSON's data model.
  """

  def visit_value(self, node: NodeView) -> JSONValue:
    """Delegate to the actual value node."""
    # Value node has one child - the actual value
    for child in node.children:
      if not child.is_token:  # Skip any tokens, visit nodes
        return self.visit(child)
      elif child.kind in ("STRING", "NUMBER", "TRUE", "FALSE", "NULL"):
        # Direct primitive token
        return self.visit(child)
    raise ValueError("No value found in value node")

  def visit_object(self, node: NodeView) -> JSONObject:
    """Build object from members."""
    members = {}

    for child in node.children:
      if child.kind == "member":
        key, value = self.visit_member(child)
        members[key] = value

    return JSONObject(members)

  def visit_member(self, node: NodeView) -> tuple[str, JSONValue]:
    """Extract key-value pair from member."""
    key = None
    value = None

    for child in node.children:
      if child.kind == "STRING" and key is None:
        key = self._extract_string_value(child.text)
      elif child.kind == "value":
        value = self.visit(child)

    return key, value

  def visit_array(self, node: NodeView) -> JSONArray:
    """Build array from elements."""
    elements = []

    for child in node.children:
      if child.kind == "value":
        elements.append(self.visit(child))

    return JSONArray(elements)

  def visit_STRING(self, node: NodeView) -> JSONString:
    """Convert string token to AST node."""
    return JSONString(self._extract_string_value(node.text))

  def visit_NUMBER(self, node: NodeView) -> JSONNumber:
    """Convert number token to AST node."""
    text = node.text
    if "." in text or "e" in text or "E" in text:
      return JSONNumber(float(text))
    return JSONNumber(int(text))

  def visit_TRUE(self, node: NodeView) -> JSONBoolean:
    """True literal."""
    return JSONBoolean(True)

  def visit_FALSE(self, node: NodeView) -> JSONBoolean:
    """False literal."""
    return JSONBoolean(False)

  def visit_NULL(self, node: NodeView) -> JSONNull:
    """Null literal."""
    return JSONNull()

  def generic_visit(self, node: NodeView) -> JSONValue:
    """Fallback for unexpected nodes."""
    raise ValueError(f"Unexpected node type: {node.kind}")

  def _extract_string_value(self, quoted: str) -> str:
    """Remove quotes and process escape sequences."""
    # Remove surrounding quotes
    content = quoted[1:-1]

    # Process basic escape sequences
    replacements = {
      r"\"": '"',
      r"\\": "\\",
      r"\/": "/",
      r"\b": "\b",
      r"\f": "\f",
      r"\n": "\n",
      r"\r": "\r",
      r"\t": "\t",
    }

    for escape, char in replacements.items():
      content = content.replace(escape, char)

    return content


# ===== Phase 4: Python Object Building =====


class JSONObjectBuilder:
  """
  Converts JSON AST to native Python objects.

  This final transformation produces standard Python data structures
  that can be used directly in applications.
  """

  def build(self, ast: JSONValue) -> Any:
    """Convert AST node to Python object."""
    if isinstance(ast, JSONObject):
      return {key: self.build(value) for key, value in ast.members.items()}

    elif isinstance(ast, JSONArray):
      return [self.build(element) for element in ast.elements]

    elif isinstance(ast, JSONString):
      return ast.value

    elif isinstance(ast, JSONNumber):
      return ast.value

    elif isinstance(ast, JSONBoolean):
      return ast.value

    elif isinstance(ast, JSONNull):
      return None

    else:
      raise ValueError(f"Unknown AST node type: {type(ast)}")


# ===== Public API =====


def parse_json(text: str, obs_context: Optional[LexicalContext] = None) -> Any:
  """
  Parse JSON text into Python objects.

  This function orchestrates the complete parsing pipeline:
  1. Tokenize the input
  2. Parse tokens into CST
  3. Transform CST to AST
  4. Build Python objects from AST

  Args:
      text: JSON string to parse
      obs_context: Optional observability context

  Returns:
      Python object representation of the JSON

  Example:
      >>> parse_json('{"name": "John", "age": 30}')
      {'name': 'John', 'age': 30}
  """
  # Phase 1: Tokenize
  lexer = JSONLexer(obs_context)
  tokens = list(lexer.lex(text))

  # Phase 2: Parse to CST
  parser = JSONParser(tokens, obs_context)
  cst = parser.parse()

  # Phase 3: Build AST
  ast_builder = JSONASTBuilder()
  ast = ast_builder.visit(cst.root)

  # Phase 4: Build Python objects
  object_builder = JSONObjectBuilder()
  return object_builder.build(ast)


def parse_json_to_cst(text: str, obs_context: Optional[LexicalContext] = None) -> SyntaxTree:
  """
  Parse JSON to CST for inspection.

  Useful for debugging or syntax-aware tools that need to
  preserve formatting and structure.
  """
  lexer = JSONLexer(obs_context)
  tokens = list(lexer.lex(text))
  parser = JSONParser(tokens, obs_context)
  return parser.parse()


def parse_json_to_ast(text: str, obs_context: Optional[LexicalContext] = None) -> JSONValue:
  """
  Parse JSON to AST for analysis.

  Returns the intermediate AST representation before conversion
  to Python objects.
  """
  lexer = JSONLexer(obs_context)
  tokens = list(lexer.lex(text))
  parser = JSONParser(tokens, obs_context)
  cst = parser.parse()

  ast_builder = JSONASTBuilder()
  return ast_builder.visit(cst.root)


# ===== Example Usage =====


def main():
  """Main entry point with command-line argument handling."""
  # Parse command line arguments
  parser = argparse.ArgumentParser(description="JSON Parser Demo")
  parser.add_argument("-q", "--quiet", action="store_true", help="Suppress observability traces")
  args = parser.parse_args()

  # Initialize observability based on quiet flag
  obs_context = None
  if not args.quiet:
    print("=== Setting up Observability ===")
    config = ObservabilityConfig(
      handlers=[PrintHandler(sys.stderr, format="{timestamp_ms:8.1f}ms {type}: {value}", include_context=True)]
    )
    SharedContext.setup(config)
    print(f"Handler count: {SharedContext.get().get_handler_count()}")

    # Create lexical context that uses the shared context
    obs_context = LexicalContext()
    print("\n=== JSON Parser Test Suite (with tracing) ===\n")
  else:
    print("=== JSON Parser Test Suite (quiet mode) ===\n")

  # Test data
  test_cases = [
    '{"name": "John", "age": 30, "active": true}',
    '[1, 2, 3, "hello", null, false]',
    '{"users": [{"id": 1}, {"id": 2}], "count": 2}',
    '{"nested": {"deeply": {"value": 42}}}',
    "[]",
    "{}",
  ]

  for i, test in enumerate(test_cases, 1):
    print(f"Test {i}: {test}")

    try:
      # Parse with our implementation
      result = parse_json(test, obs_context)
      print(f"Parsed: {result}")

      # Verify against standard library
      expected = json.loads(test)
      if result == expected:
        print("✓ Matches standard library")
      else:
        print("✗ Does not match standard library")
        print(f"Expected: {expected}")

    except Exception as e:
      print(f"✗ Error: {e}")

    print()

  # Demonstrate CST inspection (without observability for cleaner output)
  print("=== CST Inspection ===")
  cst = parse_json_to_cst('{"x": [1, 2]}')
  print(cst.dump())

  # Demonstrate AST inspection
  print("\n=== AST Inspection ===")
  ast = parse_json_to_ast('{"x": [1, 2]}')
  print(f"Root type: {type(ast).__name__}")
  print(f"Members: {ast.members if hasattr(ast, 'members') else 'N/A'}")

  # Final message
  if not args.quiet:
    print("\n=== Observability enabled - traces written to stderr ===")
  else:
    print("\n=== Completed in quiet mode ===")


if __name__ == "__main__":
  main()
