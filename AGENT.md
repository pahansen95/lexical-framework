# Agentic Developer Guide

This document provides basic guidance for Agentic Developers interfacing with this project. It reflects needs & expectations at the current moment in time.

## Agent Directives

- Adhere to the principles laid out in the [Contributor's Guide](./CONTRIBUTOR.md).
- Consult the [documentation](./docs/) but the [source code](./src/) is always ground truth.
- Consult the [KnowledgeBase](./meta/kb/) for contextual & supporint information.
- Formatting & Style will be enforced but attempt your best to produce [well formed code](./pyproject.toml).

## Project Lifecycle

> This project is currently in active development.

- Do not concern yourself with backwards compatability; we do not need to implement Shims or other "change the wheels while driving" code.
- API is unstable. Refactor often & early.
- Keep files (modules) loosely coupled; it's okay to duplicate code or semantics, we can always refactor cross cutting concerns later.
- Favor organization by domain/concepts. Favor modules (files) over packages (fodlers).
- Articulate your mental models about the project's functionaity & features. Think through things deeply.
- When implementing new functionality; K.I.S.S. Be iterative & aim to deduplicate, minimize or otherwise reduce the amount of code written.
 