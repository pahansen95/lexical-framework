"""
MiniLang - Complete Implementation

A demonstration language with Python-like indentation, showcasing the
lexical framework's capabilities for stateful parsing and immutable
syntax tree construction.
"""

from typing import List, Optional, Union
from dataclasses import dataclass

from lex import Lexer, Token, pattern, token, Stack, Position, Match
from parse import Parser, rule, Visitor, ParseError
from tree import NodeView, SyntaxTree


# ===== AST Node Definitions =====


@dataclass
class ASTNode:
  """Base class for all AST nodes"""

  line: int
  column: int


@dataclass
class Program(ASTNode):
  """Root node containing all statements"""

  statements: List["Statement"]


@dataclass
class VarDecl(ASTNode):
  """Variable declaration with optional initialization"""

  name: str
  value: Optional["Expression"]


@dataclass
class Assignment(ASTNode):
  """Variable assignment"""

  name: str
  value: "Expression"


@dataclass
class IfStatement(ASTNode):
  """Conditional statement with optional else"""

  condition: "Expression"
  then_block: List["Statement"]
  else_block: Optional[List["Statement"]]


@dataclass
class WhileStatement(ASTNode):
  """While loop"""

  condition: "Expression"
  body: List["Statement"]


@dataclass
class FunctionDef(ASTNode):
  """Function definition"""

  name: str
  params: List[str]
  body: List["Statement"]


@dataclass
class Return(ASTNode):
  """Return statement"""

  value: Optional["Expression"]


@dataclass
class ExprStatement(ASTNode):
  """Expression used as statement"""

  expression: "Expression"


@dataclass
class BinaryOp(ASTNode):
  """Binary operation"""

  op: str
  left: "Expression"
  right: "Expression"


@dataclass
class UnaryOp(ASTNode):
  """Unary operation"""

  op: str
  operand: "Expression"


@dataclass
class FunctionCall(ASTNode):
  """Function call"""

  name: str
  args: List["Expression"]


@dataclass
class Identifier(ASTNode):
  """Variable reference"""

  name: str


@dataclass
class Number(ASTNode):
  """Numeric literal"""

  value: float


@dataclass
class String(ASTNode):
  """String literal"""

  value: str


@dataclass
class Boolean(ASTNode):
  """Boolean literal"""

  value: bool


# Type aliases for clarity
Expression = Union[BinaryOp, UnaryOp, FunctionCall, Identifier, Number, String, Boolean]
Statement = Union[VarDecl, Assignment, IfStatement, WhileStatement, FunctionDef, Return, ExprStatement]


# ===== Lexer Implementation =====


class MiniLangLexer(Lexer):
  """
  Lexer for MiniLang with indentation-based blocks.

  Transforms physical indentation into logical INDENT/DEDENT tokens
  that mark block boundaries in the token stream.
  """

  # State tracking
  indent_stack = Stack()  # Active indentation levels

  # Keywords with high priority to avoid identifier conflicts
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

  # Operators (multi-character first to avoid conflicts)
  POWER = pattern.literal("**", priority=6)
  EQ = pattern.literal("==", priority=6)
  NE = pattern.literal("!=", priority=6)
  LE = pattern.literal("<=", priority=6)
  GE = pattern.literal(">=", priority=6)

  # Single-character operators
  PLUS = pattern.literal("+")
  MINUS = pattern.literal("-")
  TIMES = pattern.literal("*")
  DIVIDE = pattern.literal("/")
  MODULO = pattern.literal("%")
  LT = pattern.literal("<")
  GT = pattern.literal(">")
  ASSIGN = pattern.literal("=")
  LPAREN = pattern.literal("(")
  RPAREN = pattern.literal(")")
  COMMA = pattern.literal(",")
  COLON = pattern.literal(":")

  # Literals and identifiers
  NUMBER = pattern.regex(r"\d+(\.\d+)?", priority=5)
  IDENTIFIER = pattern.regex(r"[a-zA-Z_]\w*", priority=4)

  # Structural tokens
  NEWLINE = pattern.literal("\n")
  COMMENT = pattern.regex(r"#[^\n]*", skip=True)

  # ===== Indentation Patterns =====

  @token(at_line_start=True, priority=15)
  def INDENT(self, pos: Position) -> Optional[Match]:
    """
    Generate INDENT token when indentation increases.
    Consumes the leading spaces that triggered the indent.
    """
    if not self._at_content_line_start(pos):
      return None

    space_count = self._count_indentation(pos)
    if self._is_blank_line(pos, space_count):
      return None

    current_level = self.indent_stack.current or 0

    if space_count > current_level:
      self.indent_stack.push(space_count)
      return Match("", space_count)

    return None

  @token(at_line_start=True, priority=14)
  def DEDENT(self, pos: Position) -> Optional[Match]:
    """
    Generate DEDENT token when indentation decreases.
    Multiple dedents are handled through repeated matching.
    """
    if not self._at_content_line_start(pos):
      return None

    space_count = self._count_indentation(pos)
    if self._is_blank_line(pos, space_count):
      return None

    current_level = self.indent_stack.current or 0

    if space_count < current_level:
      self.indent_stack.pop()
      return Match("", space_count)

    return None

  @token(at_line_start=True, priority=13, skip=True)
  def LINE_SPACES(self, pos: Position) -> Optional[Match]:
    """
    Consume spaces when indentation unchanged.
    Skipped to avoid cluttering token stream.
    """
    if not self._at_content_line_start(pos):
      return None

    space_count = self._count_indentation(pos)
    if self._is_blank_line(pos, space_count):
      return None

    current_level = self.indent_stack.current or 0

    if space_count == current_level and space_count > 0:
      return Match(" " * space_count, space_count)

    return None

  # ===== String Pattern =====

  @token(priority=7)
  def STRING(self, pos: Position) -> Optional[Match]:
    """
    Match quoted string literals with escape sequences.
    Supports both single and double quotes.
    """
    if pos.peek() not in ('"', "'"):
      return None

    delimiter = pos.peek()
    length = 1  # Opening quote
    escaped = False

    while True:
      char = pos.peek(length)

      if char is None:
        return None  # Unclosed string

      if escaped:
        escaped = False
      elif char == "\\":
        escaped = True
      elif char == delimiter:
        length += 1  # Closing quote
        text = pos.text[pos.pos : pos.pos + length]
        return Match(text, length)
      elif char == "\n":
        return None  # Unclosed string

      length += 1

  # ===== Whitespace Pattern =====

  @token(skip=True)
  def WHITESPACE(self, pos: Position) -> Optional[Match]:
    """
    Skip non-structural whitespace.
    Only matches spaces not at line start.
    """
    if pos.at_line_start:
      return None

    count = 0
    while pos.peek(count) in " \t":
      count += 1

    if count > 0:
      text = pos.text[pos.pos : pos.pos + count]
      return Match(text, count)

    return None

  # ===== Helper Methods =====

  def _at_content_line_start(self, pos: Position) -> bool:
    """Check if at start of line with content ahead."""
    return pos.at_line_start and not pos.at_end

  def _count_indentation(self, pos: Position) -> int:
    """Count leading spaces/tabs without advancing position."""
    count = 0
    while pos.peek(count) in " \t":
      count += 1
    return count

  def _is_blank_line(self, pos: Position, indent_count: int) -> bool:
    """Check if line contains only whitespace or comments."""
    next_char = pos.peek(indent_count)
    return next_char in ("\n", "#", None)


# ===== Parser Implementation =====


class MiniLangParser(Parser):
  """
  Recursive descent parser for MiniLang.
  Builds immutable syntax trees using the framework's builder.
  """

  def __init__(self, tokens: List[Token]):
    super().__init__(tokens)
    self.skip_structural = False  # Keep all tokens for CST
    self.structural_tokens = {"WHITESPACE", "COMMENT"}

  # ===== Grammar Root =====

  @rule
  def program(self):
    """Parse a complete program."""
    # Skip leading newlines
    while self.match("NEWLINE"):
      self.consume()

    # Parse statements until EOF
    while not self.match("EOF"):
      self.statement()

      # Consume trailing newlines
      while self.match("NEWLINE"):
        self.consume()

  def parse_root(self):
    """Entry point for parser."""
    self.program()

  # ===== Statements =====

  def statement(self):
    """Parse any statement type."""
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
    """var IDENTIFIER [= expression]"""
    self.expect("VAR")
    self.expect("IDENTIFIER")

    if self.match("ASSIGN"):
      self.consume()
      self.expression()

  @rule
  def assignment_statement(self):
    """IDENTIFIER = expression"""
    self.expect("IDENTIFIER")
    self.expect("ASSIGN")
    self.expression()

  @rule
  def if_statement(self):
    """if expression: block [else: block]"""
    self.expect("IF")
    self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    self.block()
    self.expect("DEDENT")

    if self.match("ELSE"):
      self.consume()
      self.expect("COLON")
      self.expect("NEWLINE")
      self.expect("INDENT")
      self.block()
      self.expect("DEDENT")

  @rule
  def while_statement(self):
    """while expression: block"""
    self.expect("WHILE")
    self.expression()
    self.expect("COLON")
    self.expect("NEWLINE")

    self.expect("INDENT")
    self.block()
    self.expect("DEDENT")

  @rule
  def function_def(self):
    """def IDENTIFIER(params): block"""
    self.expect("DEF")
    self.expect("IDENTIFIER")
    self.expect("LPAREN")

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
    """return [expression]"""
    self.expect("RETURN")

    if not self.match("NEWLINE"):
      self.expression()

  @rule
  def expression_statement(self):
    """expression used as statement"""
    self.expression()

  @rule
  def block(self):
    """Multiple statements in indented block"""
    while not self.match("DEDENT", "EOF"):
      self.statement()

      # Handle statement separators
      while self.match("NEWLINE"):
        self.consume()

  # ===== Expressions (Precedence Climbing) =====

  def expression(self):
    """Top-level expression parsing."""
    self.or_expr()

  @rule
  def or_expr(self):
    """Left-associative OR"""
    self.and_expr()

    while self.match("OR"):
      self.consume()
      self.and_expr()

  @rule
  def and_expr(self):
    """Left-associative AND"""
    self.not_expr()

    while self.match("AND"):
      self.consume()
      self.not_expr()

  def not_expr(self):
    """Unary NOT"""
    if self.match("NOT"):
      self._build_unary()
    else:
      self.comparison()

  @rule(name="unary_op")
  def _build_unary(self):
    """Build unary operation node"""
    self.consume()  # NOT
    self.not_expr()

  @rule
  def comparison(self):
    """Comparison operators"""
    self.additive()

    while self.match("EQ", "NE", "LT", "LE", "GT", "GE"):
      self.consume()
      self.additive()

  @rule
  def additive(self):
    """Addition and subtraction"""
    self.multiplicative()

    while self.match("PLUS", "MINUS"):
      self.consume()
      self.multiplicative()

  @rule
  def multiplicative(self):
    """Multiplication, division, modulo"""
    self.power()

    while self.match("TIMES", "DIVIDE", "MODULO"):
      self.consume()
      self.power()

  @rule
  def power(self):
    """Right-associative exponentiation"""
    self.unary()

    if self.match("POWER"):
      self.consume()
      self.power()

  def unary(self):
    """Unary plus/minus"""
    if self.match("PLUS", "MINUS"):
      self._build_prefix()
    else:
      self.postfix()

  @rule(name="unary_op")
  def _build_prefix(self):
    """Build prefix operation"""
    self.consume()
    self.unary()

  @rule
  def postfix(self):
    """Function calls"""
    self.primary()

    while self.match("LPAREN"):
      self._build_call()

  @rule(name="call")
  def _build_call(self):
    """Build function call"""
    self.expect("LPAREN")

    if not self.match("RPAREN"):
      self.separated(self.expression, "COMMA")

    self.expect("RPAREN")

  def primary(self):
    """Primary expressions"""
    if self.match("NUMBER"):
      self.consume()
    elif self.match("STRING"):
      self.consume()
    elif self.match("TRUE", "FALSE"):
      self.consume()
    elif self.match("IDENTIFIER"):
      self.consume()
    elif self.match("LPAREN"):
      self._build_paren()
    else:
      token = self.peek()
      raise ParseError(f"Unexpected {token.type if token else 'EOF'}")

  @rule(name="paren_expr")
  def _build_paren(self):
    """Build parenthesized expression"""
    self.expect("LPAREN")
    self.expression()
    self.expect("RPAREN")


# ===== AST Builder =====


class ASTBuilder(Visitor):
  """Transform concrete syntax tree to abstract syntax tree."""

  def visit_program(self, node: NodeView) -> Program:
    """Extract statements from program node."""
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
    """Build variable declaration."""
    name_token = self._find_token(node, "IDENTIFIER")
    value = None

    # Look for initialization
    if self._has_token(node, "ASSIGN"):
      for child in node.children:
        if self._is_expression(child):
          value = self.visit(child)
          break

    return VarDecl(line=name_token.line, column=name_token.column, name=name_token.text, value=value)

  def visit_assignment_statement(self, node: NodeView) -> Assignment:
    """Build assignment."""
    name_token = self._find_token(node, "IDENTIFIER")

    # Find expression after =
    value = None
    for child in node.children:
      if self._is_expression(child):
        value = self.visit(child)
        break

    return Assignment(line=name_token.line, column=name_token.column, name=name_token.text, value=value)

  def visit_if_statement(self, node: NodeView) -> IfStatement:
    """Build if statement."""
    if_token = self._find_token(node, "IF")
    condition = None
    then_block = []
    else_block = None

    # Extract components
    blocks_seen = 0
    for child in node.children:
      if self._is_expression(child) and condition is None:
        condition = self.visit(child)
      elif child.kind == "block":
        if blocks_seen == 0:
          then_block = self._extract_statements(child)
        else:
          else_block = self._extract_statements(child)
        blocks_seen += 1

    return IfStatement(
      line=if_token.line, column=if_token.column, condition=condition, then_block=then_block, else_block=else_block
    )

  def visit_while_statement(self, node: NodeView) -> WhileStatement:
    """Build while loop."""
    while_token = self._find_token(node, "WHILE")
    condition = None
    body = []

    for child in node.children:
      if self._is_expression(child):
        condition = self.visit(child)
      elif child.kind == "block":
        body = self._extract_statements(child)

    return WhileStatement(line=while_token.line, column=while_token.column, condition=condition, body=body)

  def visit_function_def(self, node: NodeView) -> FunctionDef:
    """Build function definition."""
    def_token = self._find_token(node, "DEF")
    name_token = None
    params = []
    body = []

    # Find name (first identifier after DEF)
    found_def = False
    for child in node.children:
      if child.kind == "DEF":
        found_def = True
      elif found_def and child.kind == "IDENTIFIER" and name_token is None:
        name_token = child
        found_def = False

    # Extract parameters
    in_params = False
    for child in node.children:
      if child.kind == "LPAREN":
        in_params = True
      elif child.kind == "RPAREN":
        in_params = False
      elif in_params and child.kind == "IDENTIFIER":
        params.append(child.text)

    # Extract body
    for child in node.children:
      if child.kind == "block":
        body = self._extract_statements(child)

    return FunctionDef(
      line=def_token.line, column=def_token.column, name=name_token.text if name_token else "", params=params, body=body
    )

  def visit_return_statement(self, node: NodeView) -> Return:
    """Build return statement."""
    return_token = self._find_token(node, "RETURN")
    value = None

    for child in node.children:
      if self._is_expression(child):
        value = self.visit(child)
        break

    return Return(line=return_token.line, column=return_token.column, value=value)

  def visit_expression_statement(self, node: NodeView) -> ExprStatement:
    """Build expression statement."""
    expr = None

    for child in node.children:
      if self._is_expression(child):
        expr = self.visit(child)
        break

    # Use expression position if available
    line = expr.line if expr else 1
    column = expr.column if expr else 1

    return ExprStatement(line=line, column=column, expression=expr)

  # ===== Expression Visitors =====

  def visit_or_expr(self, node: NodeView) -> Expression:
    """Build OR expression."""
    return self._build_binary(node)

  def visit_and_expr(self, node: NodeView) -> Expression:
    """Build AND expression."""
    return self._build_binary(node)

  def visit_comparison(self, node: NodeView) -> Expression:
    """Build comparison expression."""
    return self._build_binary(node)

  def visit_additive(self, node: NodeView) -> Expression:
    """Build additive expression."""
    return self._build_binary(node)

  def visit_multiplicative(self, node: NodeView) -> Expression:
    """Build multiplicative expression."""
    return self._build_binary(node)

  def visit_power(self, node: NodeView) -> Expression:
    """Build power expression."""
    return self._build_binary(node)

  def visit_unary_op(self, node: NodeView) -> UnaryOp:
    """Build unary operation."""
    op_token = None
    operand = None

    for child in node.children:
      if child.is_token and child.kind in ("PLUS", "MINUS", "NOT"):
        op_token = child
      elif self._is_expression(child):
        operand = self.visit(child)

    return UnaryOp(
      line=op_token.line if op_token else 1,
      column=op_token.column if op_token else 1,
      op=op_token.kind if op_token else "",
      operand=operand,
    )

  def visit_postfix(self, node: NodeView) -> Expression:
    """Build postfix expression (function calls)."""
    base = None

    for child in node.children:
      if child.kind == "primary":
        base = self.visit(child)
      elif child.kind == "call" and isinstance(base, Identifier):
        args = self._extract_arguments(child)
        base = FunctionCall(line=base.line, column=base.column, name=base.name, args=args)

    return base

  def visit_primary(self, node: NodeView) -> Expression:
    """Build primary expression."""
    for child in node.children:
      if child.kind == "NUMBER":
        value = float(child.text)
        return Number(line=child.line, column=child.column, value=value)

      elif child.kind == "STRING":
        # Remove quotes and process escapes
        text = child.text[1:-1]
        text = self._unescape_string(text)
        return String(line=child.line, column=child.column, value=text)

      elif child.kind == "TRUE":
        return Boolean(line=child.line, column=child.column, value=True)

      elif child.kind == "FALSE":
        return Boolean(line=child.line, column=child.column, value=False)

      elif child.kind == "IDENTIFIER":
        return Identifier(line=child.line, column=child.column, name=child.text)

      elif child.kind == "paren_expr":
        return self.visit_paren_expr(child)

    return None

  def visit_paren_expr(self, node: NodeView) -> Expression:
    """Extract expression from parentheses."""
    for child in node.children:
      if self._is_expression(child):
        return self.visit(child)
    return None

  # ===== Helper Methods =====

  def _build_binary(self, node: NodeView) -> Expression:
    """Build left-associative binary operations."""
    operands = []
    operators = []

    # Collect operands and operators
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
    if not operands:
      return None

    result = operands[0]
    for i, op in enumerate(operators):
      if i + 1 < len(operands):
        result = BinaryOp(line=op.line, column=op.column, op=op.kind, left=result, right=operands[i + 1])

    return result

  def _extract_statements(self, block_node: NodeView) -> List[Statement]:
    """Extract statements from block."""
    statements = []

    for child in block_node.children:
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

  def _extract_arguments(self, call_node: NodeView) -> List[Expression]:
    """Extract function call arguments."""
    args = []

    for child in call_node.children:
      if self._is_expression(child):
        args.append(self.visit(child))

    return args

  def _is_expression(self, node: NodeView) -> bool:
    """Check if node is an expression."""
    return node.kind in (
      "or_expr",
      "and_expr",
      "unary_op",
      "comparison",
      "additive",
      "multiplicative",
      "power",
      "postfix",
      "primary",
      "paren_expr",
    )

  def _find_token(self, node: NodeView, kind: str) -> Optional[NodeView]:
    """Find first token of given kind."""
    for child in node.children:
      if child.kind == kind:
        return child
    return None

  def _has_token(self, node: NodeView, kind: str) -> bool:
    """Check if node contains token of given kind."""
    return self._find_token(node, kind) is not None

  def _unescape_string(self, text: str) -> str:
    """Process escape sequences in string."""
    return text.replace(r"\n", "\n").replace(r"\t", "\t").replace(r"\\", "\\").replace(r"\"", '"').replace(r"\'", "'")


# ===== API Functions =====


def parse_minilang(code: str) -> Program:
  """
  Parse MiniLang source code into an AST.

  Returns a Program node containing all statements.
  Raises LexError or ParseError on invalid input.
  """
  # Tokenize
  lexer = MiniLangLexer()
  tokens = list(lexer.lex(code))

  # Parse to CST
  parser = MiniLangParser(tokens)
  cst = parser.parse()

  # Transform to AST
  builder = ASTBuilder()
  return builder.visit(cst.root)


def parse_to_cst(code: str) -> SyntaxTree:
  """
  Parse MiniLang source code into a concrete syntax tree.

  Preserves all tokens including whitespace and comments.
  Useful for tools that need full source fidelity.
  """
  lexer = MiniLangLexer()
  tokens = list(lexer.lex(code))
  parser = MiniLangParser(tokens)
  return parser.parse()


def print_ast(node: ASTNode, indent: int = 0):
  """Pretty print an AST node with indentation."""
  prefix = "  " * indent

  if isinstance(node, Program):
    print(f"{prefix}Program:")
    for stmt in node.statements:
      print_ast(stmt, indent + 1)

  elif isinstance(node, VarDecl):
    print(f"{prefix}VarDecl: {node.name}")
    if node.value:
      print_ast(node.value, indent + 1)

  elif isinstance(node, Assignment):
    print(f"{prefix}Assignment: {node.name}")
    print_ast(node.value, indent + 1)

  elif isinstance(node, IfStatement):
    print(f"{prefix}If:")
    print(f"{prefix}  condition:")
    print_ast(node.condition, indent + 2)
    print(f"{prefix}  then:")
    for stmt in node.then_block:
      print_ast(stmt, indent + 2)
    if node.else_block:
      print(f"{prefix}  else:")
      for stmt in node.else_block:
        print_ast(stmt, indent + 2)

  elif isinstance(node, WhileStatement):
    print(f"{prefix}While:")
    print(f"{prefix}  condition:")
    print_ast(node.condition, indent + 2)
    print(f"{prefix}  body:")
    for stmt in node.body:
      print_ast(stmt, indent + 2)

  elif isinstance(node, FunctionDef):
    params = ", ".join(node.params)
    print(f"{prefix}Function: {node.name}({params})")
    for stmt in node.body:
      print_ast(stmt, indent + 1)

  elif isinstance(node, Return):
    print(f"{prefix}Return:")
    if node.value:
      print_ast(node.value, indent + 1)

  elif isinstance(node, ExprStatement):
    print(f"{prefix}ExprStatement:")
    print_ast(node.expression, indent + 1)

  elif isinstance(node, BinaryOp):
    print(f"{prefix}BinaryOp: {node.op}")
    print_ast(node.left, indent + 1)
    print_ast(node.right, indent + 1)

  elif isinstance(node, UnaryOp):
    print(f"{prefix}UnaryOp: {node.op}")
    print_ast(node.operand, indent + 1)

  elif isinstance(node, FunctionCall):
    print(f"{prefix}Call: {node.name}")
    for arg in node.args:
      print_ast(arg, indent + 1)

  elif isinstance(node, Identifier):
    print(f"{prefix}Identifier: {node.name}")

  elif isinstance(node, Number):
    print(f"{prefix}Number: {node.value}")

  elif isinstance(node, String):
    print(f"{prefix}String: {repr(node.value)}")

  elif isinstance(node, Boolean):
    print(f"{prefix}Boolean: {node.value}")


# ===== Example Usage =====

if __name__ == "__main__":
  # Example 1: Variables and expressions
  example1 = """
var x = 10
var y = 20
var z = x + y * 2
"""

  print("=== Example 1: Variables and Expressions ===")
  print("Source:")
  print(example1)
  print("\nAST:")
  ast1 = parse_minilang(example1)
  print_ast(ast1)
  print()

  # Example 2: Control flow
  example2 = """
var count = 0
while count < 5:
    count = count + 1
    if count % 2 == 0:
        print("even")
    else:
        print("odd")
"""

  print("=== Example 2: Control Flow ===")
  print("Source:")
  print(example2)
  print("\nAST:")
  ast2 = parse_minilang(example2)
  print_ast(ast2)
  print()

  # Example 3: Functions
  example3 = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

var result = factorial(5)
"""

  print("=== Example 3: Functions ===")
  print("Source:")
  print(example3)
  print("\nAST:")
  ast3 = parse_minilang(example3)
  print_ast(ast3)
  print()

  # Example 4: Inspect CST structure
  example4 = """if x > 0:
    print("positive")
"""

  print("=== Example 4: CST Structure ===")
  print("Source:")
  print(example4)
  print("\nCST:")
  cst = parse_to_cst(example4)
  print(cst.dump(indent=0))
