# Agentic Development Instructions

This file provides guidance to agentic development agents when working with code in this repository.

## Imperatives

- Work on exactly one file at a time.
- Keep your attention on a single objective before switching tasks.
- Before acting state **what** you intend to do and **why**, and request the user's feedback.
- **Always** consult the project-level README to anchor your understanding.
- When you enter a sub-folder look for a local README to gather scoped context & a local TODO to pick back up where you left.
- Concentrate on advancing the user's project development & goals.
- **DO NOT** run the project
- **DO NOT** stage or commit files with Git.

## Planning

- **Keep it simple**: implement only the core features first; refine or refactor as we go.
- **Test after each pass**: write tests when an iteration finishes, just before debugging.
- **Manage Work** in a `TODO.md` placed in the closest relevant directory. Track, milestones & their individual tasks.
- **Favor small, single-purpose files**: group features and nest concepts from broad to specific into individual files. Seek to minimize your implementation.
- **Propose refactors when**:
  - a file, class, or concept acquires too many responsibilities
  - a concept is duplicated across the codebase and a shared abstraction would simplify things—stay alert for cross-feature coupling
- **Explicit Mental Models**: Track your set of mental models surrounding the implementation domain under `models` using the `alloy` specification language. Use this to articulate, validate & constrain yourself.

## Coding Style Contract

A pragmatic, declarative coding style optimised for clarity, correctness, and auditability in long-lived systems.

### General Principles

- **Style**: Declarative > procedural; concise > clever; readable > minimal.
- **Correctness**: Prefer explicit constraints (types, assertions, validations) over implicit behaviour.
- **Documentation**: Write to explain **what** the code does and **why** it exists—don't narrate *how*.

### Formatting

> NOTE: Styling will be enforced

- **Encoding**: UTF-8; LF; limit characterset to ASCII
- **Indentation**: 2 spaces (no tabs)
- **Line Length**: No limits
- **Whitespace**:
  - Group related logic with vertical spacing
  - Avoid excessive blank lines

### Typing & Validation

- **Type Hints**: Required for all public functions and module-level values
- **Runtime Validation**: Use `pydantic` models for all structured input data

### Naming Conventions

| Element   | Style        | Example        |
| --------- | ------------ | -------------- |
| Classes   | `PascalCase` | `UserSession`  |
| Functions | `snake_case` | `parse_config` |
| Variables | `snake_case` | `file_path`    |
| Constants | `UPPERCASE`  | `MAX_RETRIES`  |

### Imports

- **Order**: Standard Library → Third-Party → Local

- **Syntax**:

  - `import foo, bar`

  - `from foo import x, y`

  - Use tuple form for long imports:

    ```python
    from some.module import (
        a_long_function,
        another_thing,
        YET_ANOTHER,
    )
    ```

- **Avoid**: `from x import *`, except in well-scoped module interfaces

### Error Handling

- Always raise specific exception types

- Include descriptive, contextual error messages

  ```python
  raise ValueError("Expected a non-empty list, got empty.")
  ```

### Assertions & Invariants

- Declare assumptions about program state at function boundaries
- Use assertions for sanity checks that should *never* fail during valid execution
- Be liberal in their usage.

### Documentation

- **Docstrings**: Required on public classes and functions
  - Explain *what* it does and *why* it's needed
- **Inline Comments**:
  - Required for any non-obvious logic or constraint
  - Avoid restating the code

### Misc

- Derive minimal declarative spec before generating logic
- Prioritise correctness and testability over code compactness
- Refactor for clarity as code evolves
- Treat type and lint failures as blocking issues
- Escalate ambiguous requirements—do not assume
- Ask the user for guidance rather than assuming when ambiguity arises
