"""
Mini Calculator Language

A minimal expression language demonstrating the lexical framework's
complete pipeline from source text to executable Python code.

Grammar:
    program     = statement*
    statement   = assignment | expression
    assignment  = "let" IDENTIFIER "=" expression
    expression  = term (('+' | '-') term)*
    term        = factor (('*' | '/') factor)*
    factor      = NUMBER | IDENTIFIER | '(' expression ')'
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import argparse
import sys

from lexical.tokenize import Lexer, pattern
from lexical.parse import Parser, rule, ParseError
from lexical.tree import NodeView, TreeVisitor
from lexical.observe import LexicalContext
from observability import SharedContext, ObservabilityConfig
from observability.handlers import PrintHandler


# ===== Phase 1: Tokenization =====


class CalcLexer(Lexer):
  """
  Tokenizes arithmetic expressions with variable support.

  Recognizes numbers, operators, identifiers, and the 'let' keyword
  for variable assignment.
  """

  # Keywords have high priority
  LET = pattern.literal("let", priority=10)

  # Literals and identifiers
  NUMBER = pattern.regex(r"\d+", priority=5)
  IDENTIFIER = pattern.regex(r"[a-zA-Z_]\w*", priority=4)

  # Operators
  PLUS = pattern.literal("+")
  MINUS = pattern.literal("-")
  TIMES = pattern.literal("*")
  DIVIDE = pattern.literal("/")
  ASSIGN = pattern.literal("=")

  # Grouping
  LPAREN = pattern.literal("(")
  RPAREN = pattern.literal(")")

  # Statement separator
  SEMICOLON = pattern.literal(";")

  # Skip whitespace
  WHITESPACE = pattern.regex(r"[ \t\r\n]+", skip=True)


# ===== Phase 2: CST Construction =====


class CalcParser(Parser):
  """
  Parses calculator expressions into a Concrete Syntax Tree.

  Implements operator precedence through recursive descent,
  preserving all syntactic elements in the CST.
  """

  def __init__(self, tokens, obs_context: Optional[LexicalContext] = None):
    super().__init__(tokens, obs_context)
    self.skip_structural = True  # No structural tokens in this language

  def parse_root(self):
    """Entry point: parse a program (sequence of statements)."""
    with self.rule("program"):
      while not self.match("EOF"):
        self.statement()

  @rule()
  def statement(self):
    """Parse assignment or expression statement."""
    if self.match("LET"):
      self.assignment()
    else:
      self.expression()

    # Optional semicolon
    if self.match("SEMICOLON"):
      self.consume()

  @rule()
  def assignment(self):
    """Parse 'let' IDENTIFIER '=' expression."""
    self.expect("LET")
    self.expect("IDENTIFIER")
    self.expect("ASSIGN")
    self.expression()

  @rule()
  def expression(self):
    """Parse addition/subtraction with left associativity."""
    self.term()

    while self.match("PLUS", "MINUS"):
      self.consume()  # operator
      self.term()

  @rule()
  def term(self):
    """Parse multiplication/division with left associativity."""
    self.factor()

    while self.match("TIMES", "DIVIDE"):
      self.consume()  # operator
      self.factor()

  def factor(self):
    """Parse atomic expressions: numbers, identifiers, or grouped expressions."""
    if self.match("NUMBER"):
      self.consume()
    elif self.match("IDENTIFIER"):
      self.consume()
    elif self.match("LPAREN"):
      with self.rule("grouped"):
        self.consume()  # (
        self.expression()
        self.expect("RPAREN")
    else:
      token = self.peek()
      if token:
        raise ParseError(f"Unexpected {token.type} at line {token.line}")
      else:
        raise ParseError("Unexpected end of input")


# ===== Phase 3: AST Generation =====


# AST Node definitions
@dataclass
class ASTNode:
  """Base class for all AST nodes."""

  pass


@dataclass
class Program(ASTNode):
  """Root node containing statements."""

  statements: List["Statement"]


@dataclass
class Assignment(ASTNode):
  """Variable assignment: let name = value."""

  name: str
  value: "Expression"


@dataclass
class BinaryOp(ASTNode):
  """Binary operation: left op right."""

  op: str
  left: "Expression"
  right: "Expression"


@dataclass
class Number(ASTNode):
  """Numeric literal."""

  value: int


@dataclass
class Variable(ASTNode):
  """Variable reference."""

  name: str


# Type aliases
Expression = Union[BinaryOp, Number, Variable]
Statement = Union[Assignment, Expression]


class ASTBuilder(TreeVisitor[ASTNode]):
  """
  Transforms CST into Abstract Syntax Tree.

  Removes syntactic noise and builds semantic nodes representing
  the program's logical structure.
  """

  def visit_program(self, node: NodeView) -> Program:
    """Build program from statements."""
    statements = []

    for child in node.children:
      if child.kind == "statement":
        stmt = self.visit(child)
        if stmt:  # Filter out None results
          statements.append(stmt)

    return Program(statements)

  def visit_statement(self, node: NodeView) -> Optional[Statement]:
    """Extract assignment or expression from statement."""
    for child in node.children:
      if child.kind == "assignment":
        return self.visit(child)
      elif child.kind == "expression":
        return self.visit(child)
    return None

  def visit_assignment(self, node: NodeView) -> Assignment:
    """Build assignment from 'let' name '=' expression."""
    name = None
    value = None

    for child in node.children:
      if child.kind == "IDENTIFIER":
        name = child.text
      elif child.kind == "expression":
        value = self.visit(child)

    return Assignment(name, value)

  def visit_expression(self, node: NodeView) -> Expression:
    """Build expression with left-associative operators."""
    return self._build_binary_ops(node, {"PLUS": "+", "MINUS": "-"})

  def visit_term(self, node: NodeView) -> Expression:
    """Build term with left-associative operators."""
    return self._build_binary_ops(node, {"TIMES": "*", "DIVIDE": "/"})

  def visit_grouped(self, node: NodeView) -> Expression:
    """Extract expression from parentheses."""
    for child in node.children:
      if child.kind == "expression":
        return self.visit(child)
    raise ValueError("No expression in grouped node")

  def visit_NUMBER(self, node: NodeView) -> Number:
    """Convert number token to AST node."""
    return Number(int(node.text))

  def visit_IDENTIFIER(self, node: NodeView) -> Variable:
    """Convert identifier token to variable reference."""
    return Variable(node.text)

  def _build_binary_ops(self, node: NodeView, op_map: Dict[str, str]) -> Expression:
    """Build left-associative binary operations."""
    operands = []
    operators = []

    for child in node.children:
      if child.kind in ("term", "factor", "expression"):
        operands.append(self.visit(child))
      elif child.kind in op_map:
        operators.append(op_map[child.kind])
      elif child.kind == "NUMBER":
        operands.append(self.visit(child))
      elif child.kind == "IDENTIFIER":
        operands.append(self.visit(child))
      elif child.kind == "grouped":
        operands.append(self.visit(child))

    # Build left-associative tree
    if not operands:
      raise ValueError("No operands found")

    result = operands[0]
    for i, op in enumerate(operators):
      if i + 1 < len(operands):
        result = BinaryOp(op, result, operands[i + 1])

    return result

  def generic_visit(self, node: NodeView) -> ASTNode:
    """Fallback for unhandled nodes."""
    # Try to find a child we can process
    for child in node.children:
      if not child.is_token:
        return self.visit(child)
    raise ValueError(f"Cannot process node: {node.kind}")


# ===== Phase 4: Python Code Generation =====


class PythonCodeGenerator:
  """
  Transforms AST into executable Python code.

  Generates Python source that can be executed to evaluate
  the original expression.
  """

  def __init__(self):
    self.code_lines: List[str] = []
    self.indent_level = 0

  def generate(self, ast: Program) -> str:
    """Generate Python code from AST."""
    self.code_lines = []
    self.indent_level = 0

    # Generate code for each statement
    for stmt in ast.statements:
      self._generate_statement(stmt)

    return "\n".join(self.code_lines)

  def _generate_statement(self, stmt: Statement) -> None:
    """Generate code for a statement."""
    if isinstance(stmt, Assignment):
      line = f"{stmt.name} = {self._generate_expression(stmt.value)}"
      self._emit_line(line)
    else:
      # Expression statement - evaluate and store as last result
      line = f"_result = {self._generate_expression(stmt)}"
      self._emit_line(line)

  def _generate_expression(self, expr: Expression) -> str:
    """Generate code for an expression."""
    if isinstance(expr, Number):
      return str(expr.value)

    elif isinstance(expr, Variable):
      return expr.name

    elif isinstance(expr, BinaryOp):
      left = self._generate_expression(expr.left)
      right = self._generate_expression(expr.right)
      # Add parentheses to preserve precedence
      return f"({left} {expr.op} {right})"

    else:
      raise ValueError(f"Unknown expression type: {type(expr)}")

  def _emit_line(self, line: str) -> None:
    """Add a line of code with proper indentation."""
    indent = "    " * self.indent_level
    self.code_lines.append(f"{indent}{line}")


# ===== Phase 5: Evaluation =====


def evaluate_calc(
  source: str, variables: Optional[Dict[str, Any]] = None, obs_context: Optional[LexicalContext] = None
) -> Any:
  """
  Evaluate calculator source code and return the result.

  Args:
      source: Calculator language source code
      variables: Optional initial variable values
      obs_context: Optional observability context

  Returns:
      The value of the last expression or None

  Example:
      >>> evaluate_calc("let x = 10; let y = 20; x + y")
      30
  """
  # Phase 1: Tokenize
  lexer = CalcLexer(obs_context)
  tokens = list(lexer.lex(source))

  # Phase 2: Parse to CST
  parser = CalcParser(tokens, obs_context)
  cst = parser.parse()

  # Phase 3: Build AST
  ast_builder = ASTBuilder()
  ast = ast_builder.visit(cst.root)

  # Phase 4: Generate Python code
  code_gen = PythonCodeGenerator()
  python_code = code_gen.generate(ast)

  # Phase 5: Execute Python code
  namespace = {"_result": None}
  if variables:
    namespace.update(variables)

  exec(python_code, namespace)

  return namespace.get("_result")


# ===== Example Usage =====


def main():
  """Main entry point with command-line argument handling."""
  # Parse command line arguments
  parser = argparse.ArgumentParser(description="Mini Calculator Language Demo")
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
    print("\n=== Mini Calculator Language Demo (with tracing) ===\n")
  else:
    print("=== Mini Calculator Language Demo (quiet mode) ===\n")

  # Test cases demonstrating the language features
  examples = [
    ("42", "Simple number"),
    ("2 + 3 * 4", "Operator precedence"),
    ("(2 + 3) * 4", "Parentheses"),
    ("let x = 10; x + 5", "Variable assignment"),
    ("let a = 5; let b = 3; a * b + 2", "Multiple variables"),
    ("let x = 10; let y = x * 2; y + x", "Variable references"),
  ]

  for source, description in examples:
    print(f"{description}: {source}")
    try:
      result = evaluate_calc(source, obs_context=obs_context)
      print(f"Result: {result}")

      # Also show the generated Python code (always without observability)
      lexer = CalcLexer()  # No context for cleaner output
      tokens = list(lexer.lex(source))
      parser = CalcParser(tokens)
      cst = parser.parse()
      ast = ASTBuilder().visit(cst.root)
      python_code = PythonCodeGenerator().generate(ast)
      print(f"Python: {python_code}")

    except Exception as e:
      print(f"Error: {e}")
    print()

  # Final message
  if not args.quiet:
    print("=== Observability enabled - traces written to stderr ===")
  else:
    print("=== Completed in quiet mode ===")


if __name__ == "__main__":
  main()
