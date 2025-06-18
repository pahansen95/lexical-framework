"""
MiniLang - A Comprehensive Example of the Lexical Framework

This example demonstrates advanced features of both the lexer and parser frameworks:
- Stateful lexing with indentation tracking
- Complex token patterns (strings with escapes, multi-line comments)
- Conditional patterns based on lexer state
- Full recursive descent parser with all combinators
- CST to AST transformation using visitors
- Error handling and position tracking
"""

from typing import List, Optional, Union
from dataclasses import dataclass

# Import from framework modules
from lex import Lexer, Token, pattern, token, Counter, Stack, State, LexError, Position
from parse import Parser, Node, rule, Visitor, ParseError


# ===== AST Node Definitions =====


@dataclass
class ASTNode:
  """Base class for AST nodes."""

  line: int
  column: int


@dataclass
class Program(ASTNode):
  statements: List["Statement"]


@dataclass
class VarDecl(ASTNode):
  name: str
  value: Optional["Expression"]


@dataclass
class Assignment(ASTNode):
  name: str
  value: "Expression"


@dataclass
class IfStatement(ASTNode):
  condition: "Expression"
  then_block: List["Statement"]
  else_block: Optional[List["Statement"]]


@dataclass
class WhileStatement(ASTNode):
  condition: "Expression"
  body: List["Statement"]


@dataclass
class FunctionDef(ASTNode):
  name: str
  params: List[str]
  body: List["Statement"]


@dataclass
class Return(ASTNode):
  value: Optional["Expression"]


@dataclass
class ExprStatement(ASTNode):
  expression: "Expression"


@dataclass
class BinaryOp(ASTNode):
  op: str
  left: "Expression"
  right: "Expression"


@dataclass
class UnaryOp(ASTNode):
  op: str
  operand: "Expression"


@dataclass
class FunctionCall(ASTNode):
  name: str
  args: List["Expression"]


@dataclass
class Identifier(ASTNode):
  name: str


@dataclass
class Number(ASTNode):
  value: float


@dataclass
class String(ASTNode):
  value: str


@dataclass
class Boolean(ASTNode):
  value: bool


# Type aliases
Expression = Union[BinaryOp, UnaryOp, FunctionCall, Identifier, Number, String, Boolean]
Statement = Union[VarDecl, Assignment, IfStatement, WhileStatement, FunctionDef, Return, ExprStatement]


# ===== MiniLang Lexer =====


class MiniLangLexer(Lexer):
  """
  Lexer for MiniLang with support for:
  - Keywords and operators
  - Indentation-based blocks
  - String literals with escape sequences
  - Single and multi-line comments
  - Stateful pattern matching
  """

  # State management
  indent_stack = Stack()  # Track indentation levels
  string_delimiter = State("")  # Track current string delimiter
  paren_depth = Counter(0)  # Track parenthesis nesting

  # Keywords (high priority to beat identifiers)
  VAR = pattern.literal("var", priority=10)
  IF = pattern.literal("if", priority=10)
  ELSE = pattern.literal("else", priority=10)
  WHILE = pattern.literal("while", priority=10)
  DEF = pattern.literal("def", priority=10)
  RETURN = pattern.literal("return", priority=10)
  TRUE = pattern.literal("true", priority=10)
  FALSE = pattern.literal("false", priority=10)
  AND = pattern.literal("and", priority=10)
  OR = pattern.literal("or", priority=10)
  NOT = pattern.literal("not", priority=10)

  # Operators and punctuation
  PLUS = pattern.literal("+")
  MINUS = pattern.literal("-")
  TIMES = pattern.literal("*")
  DIVIDE = pattern.literal("/")
  MODULO = pattern.literal("%")
  POWER = pattern.literal("**")

  EQ = pattern.literal("==")
  NE = pattern.literal("!=")
  LT = pattern.literal("<")
  LE = pattern.literal("<=")
  GT = pattern.literal(">")
  GE = pattern.literal(">=")

  ASSIGN = pattern.literal("=")
  LPAREN = pattern.literal("(")
  RPAREN = pattern.literal(")")
  COMMA = pattern.literal(",")
  COLON = pattern.literal(":")

  # Identifiers and literals
  IDENTIFIER = pattern.regex(r"[a-zA-Z_]\w*", priority=5)
  NUMBER = pattern.regex(r"\d+(\.\d+)?", priority=5)

  # Comments (skip)
  COMMENT = pattern.regex(r"#[^\n]*", skip=True)

  # Newlines and whitespace need special handling for indentation
  NEWLINE = pattern.literal("\n")

  # String literals using method pattern for complex handling
  @token(priority=7)
  def STRING(self, pos: "Position") -> bool:
    """Match string literals with escape sequence handling."""
    # Check for string delimiter
    if pos.peek() not in ['"', "'"]:
      return False

    delimiter = pos.peek()
    pos.advance()  # Skip opening delimiter

    # Track string delimiter in state
    self.string_delimiter.set(delimiter)

    # Accumulate string content
    escaped = False
    while not pos.at_end:
      char = pos.peek()

      if escaped:
        # Handle escape sequences
        escaped = False
        pos.advance()
      elif char == "\\":
        escaped = True
        pos.advance()
      elif char == delimiter:
        # Found closing delimiter
        pos.advance()
        self.string_delimiter.reset()
        return True
      elif char == "\n":
        # Unclosed string
        break
      else:
        pos.advance()

    # Reset state and fail
    self.string_delimiter.reset()
    return False

  # Multi-line comments using method pattern
  @token(priority=8, skip=True)
  def BLOCK_COMMENT(self, pos: "Position") -> bool:
    """Match multi-line comments /* ... */"""
    if not (pos.peek() == "/" and pos.peek(1) == "*"):
      return False

    pos.advance(2)  # Skip /*

    # Find closing */
    while not pos.at_end:
      if pos.peek() == "*" and pos.peek(1) == "/":
        pos.advance(2)
        return True
      pos.advance()

    return False

  # Indentation handling
  @token(at_line_start=True, priority=15)
  def INDENT(self, pos: "Position") -> bool:
    """Match increased indentation at line start."""
    if pos.at_end or not pos.at_line_start:
      return False

    # Skip blank lines
    start = pos.pos
    while pos.peek() and pos.peek() in " \t":
      pos.advance()

    # If line is empty or comment, reset and skip
    if pos.at_end or pos.peek() in "\n#":
      pos.pos = start
      return False

    # Calculate indentation level
    indent_level = pos.pos - start
    current_indent = self.indent_stack.current or 0

    if indent_level > current_indent:
      # Increased indentation
      self.indent_stack.push(indent_level)
      return True
    else:
      # No increase, reset position
      pos.pos = start
      return False

  @token(at_line_start=True, priority=14)
  def DEDENT(self, pos: "Position") -> bool:
    """Match decreased indentation at line start."""
    if pos.at_end or not pos.at_line_start:
      return False

    # Skip blank lines
    start = pos.pos
    while pos.peek() and pos.peek() in " \t":
      pos.advance()

    # If line is empty or comment, reset and skip
    if pos.at_end or pos.peek() in "\n#":
      pos.pos = start
      return False

    # Calculate indentation level
    indent_level = pos.pos - start
    current_indent = self.indent_stack.current or 0

    if indent_level < current_indent:
      # Find matching indentation level
      while self.indent_stack.depth > 0 and self.indent_stack.current > indent_level:
        self.indent_stack.pop()
      pos.pos = start  # Don't consume whitespace
      return True
    else:
      # No dedent
      pos.pos = start
      return False

  # Regular whitespace (skip, but not at line start)
  @token(skip=True, when=lambda self: not self._at_line_start)
  def WHITESPACE(self, pos: "Position") -> bool:
    """Skip non-significant whitespace."""
    if pos.peek() in " \t":
      while pos.peek() in " \t":
        pos.advance()
      return True
    return False

  def _at_line_start(self) -> bool:
    """Helper to check if we're at line start."""
    # This would need access to position context
    return False


# ===== MiniLang Parser =====


class MiniLangParser(Parser):
  """
  Parser for MiniLang with full recursive descent parsing.
  Demonstrates all parser combinators and CST construction.
  """

  def __init__(self, tokens: List[Token]):
    super().__init__(tokens)
    # Configure structural token handling
    self.skip_structural = True
    self.structural_tokens = {"WHITESPACE", "COMMENT", "BLOCK_COMMENT"}

  # ===== Program Structure =====

  @rule
  def program(self):
    """Parse complete program."""
    statements = []

    # Skip initial newlines
    while self.match("NEWLINE"):
      self.consume()

    # Parse statements until EOF
    while not self.match("EOF"):
      stmt = self.statement()
      statements.append(stmt)

      # Consume statement-ending newlines
      while self.match("NEWLINE"):
        self.consume()

    return statements

  # ===== Statements =====

  def statement(self):
    """Parse any statement."""
    return self.choice(
      self.var_declaration,
      self.assignment_statement,
      self.if_statement,
      self.while_statement,
      self.function_def,
      self.return_statement,
      self.expression_statement,
    )

  @rule
  def var_declaration(self):
    """Parse variable declaration: var name = expr"""
    self.expect("VAR")
    name = self.expect("IDENTIFIER")

    value = None
    if self.match("ASSIGN"):
      self.consume()
      value = self.expression()

    return ("var_decl", name, value)

  @rule
  def assignment_statement(self):
    """Parse assignment: name = expr"""
    name = self.expect("IDENTIFIER")
    self.expect("ASSIGN")
    value = self.expression()
    return ("assign", name, value)

  @rule
  def if_statement(self):
    """Parse if statement with optional else."""
    self.expect("IF")
    condition = self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    # Parse indented then-block
    self.expect("INDENT")
    then_block = self.block()
    self.expect("DEDENT")

    # Optional else clause
    else_block = None
    if self.match("ELSE"):
      self.consume()
      self.expect("COLON")
      self.expect("NEWLINE")
      self.expect("INDENT")
      else_block = self.block()
      self.expect("DEDENT")

    return ("if", condition, then_block, else_block)

  @rule
  def while_statement(self):
    """Parse while loop."""
    self.expect("WHILE")
    condition = self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    body = self.block()
    self.expect("DEDENT")

    return ("while", condition, body)

  @rule
  def function_def(self):
    """Parse function definition."""
    self.expect("DEF")
    name = self.expect("IDENTIFIER")
    self.expect("LPAREN")

    # Parse parameter list
    params = []
    if not self.match("RPAREN"):
      params = self.separated(lambda: self.expect("IDENTIFIER"), "COMMA")

    self.expect("RPAREN")
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    body = self.block()
    self.expect("DEDENT")

    return ("function", name, params, body)

  @rule
  def return_statement(self):
    """Parse return statement."""
    self.expect("RETURN")
    value = self.optional(self.expression)
    return ("return", value)

  @rule
  def expression_statement(self):
    """Parse expression as statement."""
    expr = self.expression()
    return ("expr_stmt", expr)

  def block(self):
    """Parse a block of statements."""
    statements = []

    while not self.match("DEDENT", "EOF"):
      stmt = self.statement()
      statements.append(stmt)

      # Handle newlines between statements
      while self.match("NEWLINE"):
        self.consume()

    return statements

  # ===== Expressions =====

  def expression(self):
    """Parse expression with precedence climbing."""
    return self.or_expression()

  @rule
  def or_expression(self):
    """Parse OR expressions (lowest precedence)."""
    left = self.and_expression()

    while self.match("OR"):
      op = self.consume()
      right = self.and_expression()
      left = ("binop", op.value, left, right)

    return left

  @rule
  def and_expression(self):
    """Parse AND expressions."""
    left = self.not_expression()

    while self.match("AND"):
      op = self.consume()
      right = self.not_expression()
      left = ("binop", op.value, left, right)

    return left

  def not_expression(self):
    """Parse NOT expressions."""
    if self.match("NOT"):
      op = self.consume()
      operand = self.not_expression()
      return ("unaryop", op.value, operand)

    return self.comparison()

  @rule
  def comparison(self):
    """Parse comparison expressions."""
    left = self.additive()

    while self.match("EQ", "NE", "LT", "LE", "GT", "GE"):
      op = self.consume()
      right = self.additive()
      left = ("binop", op.type, left, right)

    return left

  @rule
  def additive(self):
    """Parse addition/subtraction."""
    left = self.multiplicative()

    while self.match("PLUS", "MINUS"):
      op = self.consume()
      right = self.multiplicative()
      left = ("binop", op.type, left, right)

    return left

  @rule
  def multiplicative(self):
    """Parse multiplication/division/modulo."""
    left = self.power()

    while self.match("TIMES", "DIVIDE", "MODULO"):
      op = self.consume()
      right = self.power()
      left = ("binop", op.type, left, right)

    return left

  @rule
  def power(self):
    """Parse exponentiation (right-associative)."""
    left = self.unary()

    if self.match("POWER"):
      op = self.consume()
      # Right-associative recursion
      right = self.power()
      return ("binop", op.type, left, right)

    return left

  def unary(self):
    """Parse unary expressions."""
    if self.match("PLUS", "MINUS"):
      op = self.consume()
      operand = self.unary()
      return ("unaryop", op.type, operand)

    return self.postfix()

  @rule
  def postfix(self):
    """Parse postfix expressions (function calls)."""
    expr = self.primary()

    while self.match("LPAREN"):
      self.consume()

      # Parse arguments
      args = []
      if not self.match("RPAREN"):
        args = self.separated(self.expression, "COMMA")

      self.expect("RPAREN")
      expr = ("call", expr, args)

    return expr

  def primary(self):
    """Parse primary expressions."""
    # Parenthesized expression
    if self.match("LPAREN"):
      self.consume()
      expr = self.expression()
      self.expect("RPAREN")
      return expr

    # Literals and identifiers
    if self.match("NUMBER"):
      token = self.consume()
      return ("number", float(token.value))

    if self.match("STRING"):
      token = self.consume()
      # Process escape sequences
      value = token.value[1:-1]  # Remove quotes
      value = value.replace(r"\n", "\n")
      value = value.replace(r"\t", "\t")
      value = value.replace(r"\\", "\\")
      value = value.replace(r"\"", '"')
      value = value.replace(r"\'", "'")
      return ("string", value)

    if self.match("TRUE"):
      self.consume()
      return ("bool", True)

    if self.match("FALSE"):
      self.consume()
      return ("bool", False)

    if self.match("IDENTIFIER"):
      token = self.consume()
      return ("id", token.value)

    raise ParseError(f"Unexpected token: {self.peek()}")


# ===== CST to AST Transformer =====


class ASTBuilder(Visitor):
  """Transform CST to typed AST nodes."""

  def visit_program(self, node: Node) -> Program:
    """Build Program AST node."""
    statements = []
    for child in node.children:
      if isinstance(child, list):
        statements.extend(self.visit(item) for item in child)
      elif not isinstance(child, Token):
        statements.append(self.visit(child))

    return Program(line=1, column=1, statements=statements)

  def visit(self, node):
    """Route visits based on node structure."""
    if isinstance(node, Node):
      return super().visit(node)

    if isinstance(node, tuple):
      node_type = node[0]

      # Statements
      if node_type == "var_decl":
        name = node[1].value
        value = self.visit(node[2]) if node[2] else None
        return VarDecl(node[1].line, node[1].column, name, value)

      elif node_type == "assign":
        name = node[1].value
        value = self.visit(node[2])
        return Assignment(node[1].line, node[1].column, name, value)

      elif node_type == "if":
        condition = self.visit(node[1])
        then_block = [self.visit(s) for s in node[2]]
        else_block = [self.visit(s) for s in node[3]] if node[3] else None
        return IfStatement(1, 1, condition, then_block, else_block)

      elif node_type == "while":
        condition = self.visit(node[1])
        body = [self.visit(s) for s in node[2]]
        return WhileStatement(1, 1, condition, body)

      elif node_type == "function":
        name = node[1].value
        params = [p.value for p in node[2]]
        body = [self.visit(s) for s in node[3]]
        return FunctionDef(node[1].line, node[1].column, name, params, body)

      elif node_type == "return":
        value = self.visit(node[1]) if node[1] else None
        return Return(1, 1, value)

      elif node_type == "expr_stmt":
        return ExprStatement(1, 1, self.visit(node[1]))

      # Expressions
      elif node_type == "binop":
        op = node[1]
        left = self.visit(node[2])
        right = self.visit(node[3])
        return BinaryOp(1, 1, op, left, right)

      elif node_type == "unaryop":
        op = node[1]
        operand = self.visit(node[2])
        return UnaryOp(1, 1, op, operand)

      elif node_type == "call":
        func = self.visit(node[1])
        args = [self.visit(arg) for arg in node[2]]
        return FunctionCall(func.line, func.column, func.name, args)

      elif node_type == "id":
        return Identifier(1, 1, node[1])

      elif node_type == "number":
        return Number(1, 1, node[1])

      elif node_type == "string":
        return String(1, 1, node[1])

      elif node_type == "bool":
        return Boolean(1, 1, node[1])

    return node


# ===== Example Usage =====


def parse_minilang(code: str) -> Program:
  """Parse MiniLang code into AST."""
  try:
    # Tokenize
    lexer = MiniLangLexer()
    tokens = list(lexer.lex(code))

    # Parse to CST
    parser = MiniLangParser(tokens)
    cst = parser.program()

    # Transform to AST
    builder = ASTBuilder()
    ast = builder.visit(cst)

    return ast

  except LexError as e:
    print(f"Lexical error: {e}")
    raise
  except ParseError as e:
    print(f"Parse error: {e}")
    raise


def print_ast(node: ASTNode, indent: int = 0):
  """Pretty print AST structure."""
  prefix = "  " * indent

  if isinstance(node, Program):
    print(f"{prefix}Program:")
    for stmt in node.statements:
      print_ast(stmt, indent + 1)

  elif isinstance(node, VarDecl):
    print(f"{prefix}VarDecl({node.name})")
    if node.value:
      print_ast(node.value, indent + 1)

  elif isinstance(node, Assignment):
    print(f"{prefix}Assignment({node.name})")
    print_ast(node.value, indent + 1)

  elif isinstance(node, IfStatement):
    print(f"{prefix}If:")
    print(f"{prefix}  Condition:")
    print_ast(node.condition, indent + 2)
    print(f"{prefix}  Then:")
    for stmt in node.then_block:
      print_ast(stmt, indent + 2)
    if node.else_block:
      print(f"{prefix}  Else:")
      for stmt in node.else_block:
        print_ast(stmt, indent + 2)

  elif isinstance(node, WhileStatement):
    print(f"{prefix}While:")
    print(f"{prefix}  Condition:")
    print_ast(node.condition, indent + 2)
    print(f"{prefix}  Body:")
    for stmt in node.body:
      print_ast(stmt, indent + 2)

  elif isinstance(node, FunctionDef):
    params = ", ".join(node.params)
    print(f"{prefix}Function({node.name}({params}))")
    for stmt in node.body:
      print_ast(stmt, indent + 1)

  elif isinstance(node, Return):
    print(f"{prefix}Return")
    if node.value:
      print_ast(node.value, indent + 1)

  elif isinstance(node, ExprStatement):
    print(f"{prefix}ExprStatement:")
    print_ast(node.expression, indent + 1)

  elif isinstance(node, BinaryOp):
    print(f"{prefix}BinaryOp({node.op})")
    print_ast(node.left, indent + 1)
    print_ast(node.right, indent + 1)

  elif isinstance(node, UnaryOp):
    print(f"{prefix}UnaryOp({node.op})")
    print_ast(node.operand, indent + 1)

  elif isinstance(node, FunctionCall):
    print(f"{prefix}Call({node.name})")
    for arg in node.args:
      print_ast(arg, indent + 1)

  elif isinstance(node, Identifier):
    print(f"{prefix}Id({node.name})")

  elif isinstance(node, Number):
    print(f"{prefix}Num({node.value})")

  elif isinstance(node, String):
    print(f"{prefix}Str({repr(node.value)})")

  elif isinstance(node, Boolean):
    print(f"{prefix}Bool({node.value})")


# ===== Test Cases =====

if __name__ == "__main__":
  # Example 1: Variable declarations and expressions
  code1 = """
var x = 10
var y = 20
var z = x + y * 2
"""

  print("=== Example 1: Variables and Expressions ===")
  print("Code:")
  print(code1)
  print("\nAST:")
  ast1 = parse_minilang(code1)
  print_ast(ast1)
  print()

  # Example 2: Control flow
  code2 = """
var count = 0
while count < 5:
    count = count + 1
    if count % 2 == 0:
        print("even")
    else:
        print("odd")
"""

  print("=== Example 2: Control Flow ===")
  print("Code:")
  print(code2)
  print("\nAST:")
  ast2 = parse_minilang(code2)
  print_ast(ast2)
  print()

  # Example 3: Functions
  code3 = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

var result = factorial(5)
"""

  print("=== Example 3: Functions ===")
  print("Code:")
  print(code3)
  print("\nAST:")
  ast3 = parse_minilang(code3)
  print_ast(ast3)
  print()

  # Example 4: String handling and complex expressions
  code4 = """
var name = "Alice"
var greeting = "Hello, " + name + "!\\n"
var complex = (2 + 3) * 4 ** 2 / 2
var condition = x > 10 and y < 20 or not z
"""

  print("=== Example 4: Strings and Complex Expressions ===")
  print("Code:")
  print(code4)
  print("\nAST:")
  ast4 = parse_minilang(code4)
  print_ast(ast4)
