"""
MiniLang - Comprehensive Example using Frozen Tree Framework

Demonstrates advanced features including stateful lexing with indentation,
complex token patterns, full recursive descent parsing, and CST to AST
transformation using immutable syntax trees.
"""

from typing import List, Optional, Union
from dataclasses import dataclass

from lex import Lexer, Token, pattern, token, Stack, State, LexError, Position
from parse import Parser, rule, Visitor, ParseError
from tree import NodeView


# ===== AST Node Definitions =====


@dataclass
class ASTNode:
  """Base class for AST nodes"""

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
  - Comments
  """

  # State management
  indent_stack = Stack()  # Track indentation levels
  string_delimiter = State("")  # Track current string delimiter

  # Keywords (high priority)
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

  # Operators
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

  # Newlines need special handling for indentation
  NEWLINE = pattern.literal("\n")

  # String literals with escape sequences
  @token(priority=7)
  def STRING(self, pos: Position) -> bool:
    """Match string literals with escape handling"""
    if pos.peek() not in ['"', "'"]:
      return False

    delimiter = pos.peek()
    pos.advance()  # Skip opening delimiter

    # Track delimiter
    self.string_delimiter.set(delimiter)

    # Accumulate string
    escaped = False
    while not pos.at_end:
      char = pos.peek()

      if escaped:
        escaped = False
        pos.advance()
      elif char == "\\":
        escaped = True
        pos.advance()
      elif char == delimiter:
        pos.advance()
        self.string_delimiter.reset()
        return True
      elif char == "\n":
        # Unclosed string
        break
      else:
        pos.advance()

    # Reset state on failure
    self.string_delimiter.reset()
    return False

  # Indentation handling
  @token(at_line_start=True, priority=15)
  def INDENT(self, pos: Position) -> bool:
    """Match increased indentation"""
    if pos.at_end or not pos.at_line_start:
      return False

    # Count spaces
    start = pos.pos
    while pos.peek() and pos.peek() in " \t":
      pos.advance()

    # Skip blank lines
    if pos.at_end or pos.peek() in "\n#":
      pos.pos = start
      return False

    # Check indentation level
    indent_level = pos.pos - start
    current_indent = self.indent_stack.current or 0

    if indent_level > current_indent:
      self.indent_stack.push(indent_level)
      return True
    else:
      pos.pos = start
      return False

  @token(at_line_start=True, priority=14)
  def DEDENT(self, pos: Position) -> bool:
    """Match decreased indentation"""
    if pos.at_end or not pos.at_line_start:
      return False

    # Count spaces
    start = pos.pos
    while pos.peek() and pos.peek() in " \t":
      pos.advance()

    # Skip blank lines
    if pos.at_end or pos.peek() in "\n#":
      pos.pos = start
      return False

    # Check indentation level
    indent_level = pos.pos - start
    current_indent = self.indent_stack.current or 0

    if indent_level < current_indent:
      # Find matching level
      while self.indent_stack.depth > 0 and self.indent_stack.current > indent_level:
        self.indent_stack.pop()
      pos.pos = start  # Don't consume whitespace
      return True
    else:
      pos.pos = start
      return False

  # Whitespace (skip except at line start)
  @token(skip=True)
  def WHITESPACE(self, pos: Position) -> bool:
    """Skip non-significant whitespace"""
    if pos.at_line_start:
      return False

    if pos.peek() in " \t":
      while pos.peek() in " \t":
        pos.advance()
      return True
    return False


# ===== MiniLang Parser =====


class MiniLangParser(Parser):
  """Parser for MiniLang with frozen tree construction"""

  def __init__(self, tokens: List[Token]):
    super().__init__(tokens)
    # Keep structural tokens for proper CST
    self.skip_structural = False
    self.structural_tokens = {"WHITESPACE", "COMMENT"}

  # ===== Program Structure =====

  @rule
  def program(self):
    """Parse complete program"""
    # Skip initial newlines
    while self.match("NEWLINE"):
      self.consume()

    # Parse statements
    while not self.match("EOF"):
      self.statement()

      # Handle newlines
      while self.match("NEWLINE"):
        self.consume()

  # ===== Statements =====

  def statement(self):
    """Parse any statement"""
    self.choice(
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
    """Parse variable declaration"""
    self.expect("VAR")
    self.expect("IDENTIFIER")

    if self.match("ASSIGN"):
      self.consume()
      self.expression()

  @rule
  def assignment_statement(self):
    """Parse assignment"""
    self.expect("IDENTIFIER")
    self.expect("ASSIGN")
    self.expression()

  @rule
  def if_statement(self):
    """Parse if statement"""
    self.expect("IF")
    self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    self.block()
    self.expect("DEDENT")

    # Optional else
    if self.match("ELSE"):
      self.consume()
      self.expect("COLON")
      self.expect("NEWLINE")
      self.expect("INDENT")
      self.block()
      self.expect("DEDENT")

  @rule
  def while_statement(self):
    """Parse while loop"""
    self.expect("WHILE")
    self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    self.block()
    self.expect("DEDENT")

  @rule
  def function_def(self):
    """Parse function definition"""
    self.expect("DEF")
    self.expect("IDENTIFIER")
    self.expect("LPAREN")

    # Parameters
    if not self.match("RPAREN"):
      self.separated(lambda: self.expect("IDENTIFIER"), "COMMA")

    self.expect("RPAREN")
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    self.block()
    self.expect("DEDENT")

  @rule
  def return_statement(self):
    """Parse return statement"""
    self.expect("RETURN")
    if not self.match("NEWLINE"):
      self.expression()

  @rule
  def expression_statement(self):
    """Parse expression as statement"""
    self.expression()

  @rule
  def block(self):
    """Parse block of statements"""
    while not self.match("DEDENT", "EOF"):
      self.statement()

      while self.match("NEWLINE"):
        self.consume()

  # ===== Expressions =====

  def expression(self):
    """Parse expression with precedence"""
    self.or_expression()

  @rule
  def or_expression(self):
    """Parse OR expressions"""
    self.and_expression()

    while self.match("OR"):
      self.consume()
      self.and_expression()

  @rule
  def and_expression(self):
    """Parse AND expressions"""
    self.not_expression()

    while self.match("AND"):
      self.consume()
      self.not_expression()

  def not_expression(self):
    """Parse NOT expressions"""
    if self.match("NOT"):
      self._unary_op()
    else:
      self.comparison()

  @rule(name="unary_op")
  def _unary_op(self):
    """Parse unary operation"""
    self.consume()  # NOT
    self.not_expression()

  @rule
  def comparison(self):
    """Parse comparison expressions"""
    self.additive()

    while self.match("EQ", "NE", "LT", "LE", "GT", "GE"):
      self.consume()
      self.additive()

  @rule
  def additive(self):
    """Parse addition/subtraction"""
    self.multiplicative()

    while self.match("PLUS", "MINUS"):
      self.consume()
      self.multiplicative()

  @rule
  def multiplicative(self):
    """Parse multiplication/division"""
    self.power()

    while self.match("TIMES", "DIVIDE", "MODULO"):
      self.consume()
      self.power()

  @rule
  def power(self):
    """Parse exponentiation"""
    self.unary()

    if self.match("POWER"):
      self.consume()
      self.power()  # Right associative

  def unary(self):
    """Parse unary expressions"""
    if self.match("PLUS", "MINUS"):
      self._prefix_op()
    else:
      self.postfix()

  @rule(name="unary_op")
  def _prefix_op(self):
    """Parse prefix operation"""
    self.consume()  # operator
    self.unary()

  @rule
  def postfix(self):
    """Parse postfix expressions"""
    self.primary()

    while self.match("LPAREN"):
      self._function_call()

  @rule(name="call")
  def _function_call(self):
    """Parse function call arguments"""
    self.expect("LPAREN")

    if not self.match("RPAREN"):
      self.separated(self.expression, "COMMA")

    self.expect("RPAREN")

  def primary(self):
    """Parse primary expressions"""
    if self.match("LPAREN"):
      self._parenthesized()
    elif self.match("NUMBER"):
      self.consume()
    elif self.match("STRING"):
      self.consume()
    elif self.match("TRUE", "FALSE"):
      self.consume()
    elif self.match("IDENTIFIER"):
      self.consume()
    else:
      token = self.peek()
      raise ParseError(f"Unexpected token: {token.type if token else 'EOF'}")

  @rule(name="paren_expr")
  def _parenthesized(self):
    """Parse parenthesized expression"""
    self.expect("LPAREN")
    self.expression()
    self.expect("RPAREN")

  def parse_root(self):
    """Parse MiniLang grammar root"""
    self.program()


# ===== AST Builder =====


class ASTBuilder(Visitor):
  """Transform CST to typed AST nodes"""

  def visit_program(self, node: NodeView) -> Program:
    """Build Program node"""
    statements = []

    for child in node.children:
      if child.kind in (
        "var_declaration",
        "assignment_statement",
        "if_statement",
        "while_statement",
        "function_def",
        "return_statement",
        "expression_statement",
      ):
        statements.append(self.visit(child))

    return Program(line=1, column=1, statements=statements)

  def visit_var_declaration(self, node: NodeView) -> VarDecl:
    """Build VarDecl node"""
    # Find identifier token
    name_token = self._find_child(node, "IDENTIFIER")
    name = name_token.text

    # Check for initial value
    value = None
    if self._has_child(node, "ASSIGN"):
      # Find expression after ASSIGN
      assign_idx = self._find_child_index(node, "ASSIGN")
      for i in range(assign_idx + 1, len(node.children)):
        child = node.children[i]
        if self._is_expression(child):
          value = self.visit(child)
          break

    return VarDecl(line=name_token.line, column=name_token.column, name=name, value=value)

  def visit_assignment_statement(self, node: NodeView) -> Assignment:
    """Build Assignment node"""
    name_token = self._find_child(node, "IDENTIFIER")

    # Find expression after ASSIGN
    assign_idx = self._find_child_index(node, "ASSIGN")
    expr = None
    for i in range(assign_idx + 1, len(node.children)):
      child = node.children[i]
      if self._is_expression(child):
        expr = self.visit(child)
        break

    return Assignment(line=name_token.line, column=name_token.column, name=name_token.text, value=expr)

  def visit_if_statement(self, node: NodeView) -> IfStatement:
    """Build IfStatement node"""
    # Find condition (first expression)
    condition = None
    then_block = []
    else_block = None

    for child in node.children:
      if self._is_expression(child) and condition is None:
        condition = self.visit(child)
      elif child.kind == "block":
        if not then_block:
          then_block = self._visit_block(child)
        else:
          else_block = self._visit_block(child)

    return IfStatement(
      line=self._find_child(node, "IF").line,
      column=self._find_child(node, "IF").column,
      condition=condition,
      then_block=then_block,
      else_block=else_block,
    )

  def visit_while_statement(self, node: NodeView) -> WhileStatement:
    """Build WhileStatement node"""
    condition = None
    body = []

    for child in node.children:
      if self._is_expression(child):
        condition = self.visit(child)
      elif child.kind == "block":
        body = self._visit_block(child)

    return WhileStatement(
      line=self._find_child(node, "WHILE").line,
      column=self._find_child(node, "WHILE").column,
      condition=condition,
      body=body,
    )

  def visit_function_def(self, node: NodeView) -> FunctionDef:
    """Build FunctionDef node"""
    # Get function name
    name_idx = self._find_child_index(node, "DEF") + 1
    name_token = node.children[name_idx]

    # Get parameters
    params = []
    in_params = False
    for child in node.children:
      if child.kind == "LPAREN":
        in_params = True
      elif child.kind == "RPAREN":
        in_params = False
      elif in_params and child.kind == "IDENTIFIER":
        params.append(child.text)

    # Get body
    body = []
    for child in node.children:
      if child.kind == "block":
        body = self._visit_block(child)

    return FunctionDef(line=name_token.line, column=name_token.column, name=name_token.text, params=params, body=body)

  def visit_return_statement(self, node: NodeView) -> Return:
    """Build Return node"""
    value = None

    for child in node.children:
      if self._is_expression(child):
        value = self.visit(child)
        break

    return Return(
      line=self._find_child(node, "RETURN").line, column=self._find_child(node, "RETURN").column, value=value
    )

  def visit_expression_statement(self, node: NodeView) -> ExprStatement:
    """Build ExprStatement node"""
    expr = None

    for child in node.children:
      if self._is_expression(child):
        expr = self.visit(child)
        break

    return ExprStatement(line=1, column=1, expression=expr)

  def _visit_block(self, node: NodeView) -> List[Statement]:
    """Extract statements from block"""
    statements = []

    for child in node.children:
      if child.kind in (
        "var_declaration",
        "assignment_statement",
        "if_statement",
        "while_statement",
        "function_def",
        "return_statement",
        "expression_statement",
      ):
        statements.append(self.visit(child))

    return statements

  # Expression visitors

  def visit_or_expression(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "or")

  def visit_and_expression(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "and")

  def visit_comparison(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "comparison")

  def visit_additive(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "additive")

  def visit_multiplicative(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "multiplicative")

  def visit_power(self, node: NodeView) -> Expression:
    return self._visit_binary_op(node, "power")

  def _visit_binary_op(self, node: NodeView, op_type: str) -> Expression:
    """Build binary operation"""
    operands = []
    operators = []

    for child in node.children:
      if self._is_expression(child):
        operands.append(self.visit(child))
      elif child.is_token and child.kind in (
        "PLUS",
        "MINUS",
        "TIMES",
        "DIVIDE",
        "MODULO",
        "POWER",
        "EQ",
        "NE",
        "LT",
        "LE",
        "GT",
        "GE",
        "AND",
        "OR",
      ):
        operators.append(child)

    # Build left-associative tree
    result = operands[0]
    for i, op in enumerate(operators):
      result = BinaryOp(line=op.line, column=op.column, op=op.kind, left=result, right=operands[i + 1])

    return result

  def visit_unary_op(self, node: NodeView) -> UnaryOp:
    """Build unary operation"""
    op_token = None
    operand = None

    for child in node.children:
      if child.is_token and child.kind in ("PLUS", "MINUS", "NOT"):
        op_token = child
      elif self._is_expression(child):
        operand = self.visit(child)

    return UnaryOp(line=op_token.line, column=op_token.column, op=op_token.kind, operand=operand)

  def visit_postfix(self, node: NodeView) -> Expression:
    """Build postfix expression (function calls)"""
    result = None

    for child in node.children:
      if child.kind == "primary":
        result = self.visit(child)
      elif child.kind == "call":
        # Extract function name and args
        if isinstance(result, Identifier):
          args = self._extract_call_args(child)
          result = FunctionCall(line=result.line, column=result.column, name=result.name, args=args)

    return result

  def _extract_call_args(self, node: NodeView) -> List[Expression]:
    """Extract arguments from call node"""
    args = []

    for child in node.children:
      if self._is_expression(child):
        args.append(self.visit(child))

    return args

  def visit_primary(self, node: NodeView) -> Expression:
    """Visit primary expression"""
    for child in node.children:
      if child.kind == "NUMBER":
        return Number(line=child.line, column=child.column, value=float(child.text))
      elif child.kind == "STRING":
        # Remove quotes and process escapes
        value = child.text[1:-1]
        value = (
          value.replace(r"\n", "\n").replace(r"\t", "\t").replace(r"\\", "\\").replace(r"\"", '"').replace(r"\'", "'")
        )
        return String(line=child.line, column=child.column, value=value)
      elif child.kind == "TRUE":
        return Boolean(line=child.line, column=child.column, value=True)
      elif child.kind == "FALSE":
        return Boolean(line=child.line, column=child.column, value=False)
      elif child.kind == "IDENTIFIER":
        return Identifier(line=child.line, column=child.column, name=child.text)
      elif child.kind == "paren_expr":
        # Extract expression from parentheses
        for subchild in child.children:
          if self._is_expression(subchild):
            return self.visit(subchild)

    return None

  # Helper methods

  def _is_expression(self, node: NodeView) -> bool:
    """Check if node is an expression"""
    return node.kind in (
      "or_expression",
      "and_expression",
      "unary_op",
      "comparison",
      "additive",
      "multiplicative",
      "power",
      "postfix",
      "primary",
      "paren_expr",
    )

  def _find_child(self, node: NodeView, kind: str) -> NodeView:
    """Find first child of given kind"""
    for child in node.children:
      if child.kind == kind:
        return child
    return None

  def _find_child_index(self, node: NodeView, kind: str) -> int:
    """Find index of first child of given kind"""
    for i, child in enumerate(node.children):
      if child.kind == kind:
        return i
    return -1

  def _has_child(self, node: NodeView, kind: str) -> bool:
    """Check if node has child of given kind"""
    return self._find_child(node, kind) is not None


# ===== Helper Functions =====


def parse_minilang(code: str) -> Program:
  """Parse MiniLang code into AST"""
  try:
    # Tokenize
    lexer = MiniLangLexer()
    tokens = list(lexer.lex(code))

    # Parse to CST
    parser = MiniLangParser(tokens)
    cst = parser.parse()

    # Transform to AST
    builder = ASTBuilder()
    ast = builder.visit(cst.root)

    return ast

  except LexError as e:
    print(f"Lexical error: {e}")
    raise
  except ParseError as e:
    print(f"Parse error: {e}")
    raise


def print_ast(node: ASTNode, indent: int = 0):
  """Pretty print AST structure"""
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
  # Example 1: Variables and expressions
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
