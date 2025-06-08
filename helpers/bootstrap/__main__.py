#!/usr/bin/env python3
"""Bootstrap module - executable entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
import importlib

from helpers.utils import configure_logging, find_project_root
from . import LAYERS
from .platform import get_platform_handler
from .state import BootstrapState

logger = logging.getLogger(__name__)


def run_layer(layer_num: int, state: BootstrapState) -> BootstrapState:
  """Execute a single bootstrap layer."""

  layer_modules = {
    0: "helpers.bootstrap.00_foundation",
    1: "helpers.bootstrap.10_prereqs",
    2: "helpers.bootstrap.20_tools",
    3: "helpers.bootstrap.30_proj",
    4: "helpers.bootstrap.40_dx",
  }

  module_name = layer_modules.get(layer_num)
  if module_name is None:
    state.errors.append(f"Unknown layer: {layer_num}")
    return state

  logger.info("Running Layer %d: %s", layer_num, LAYERS[layer_num])
  module = importlib.import_module(module_name)
  return module.run(state)


def print_summary(state: BootstrapState) -> None:
  """Display bootstrap results summary."""
  print("\n" + "=" * 60)
  print("Bootstrap Summary")
  print("=" * 60)

  if not state.layers:
    print("No layer information available")
    return

  for layer_data in state.layers:
    layer_num = layer_data.get("layer", "?")
    layer_name = layer_data.get("name", "unknown")
    print(f"\nLayer {layer_num}: {layer_name}")
    print("-" * 40)

    results = layer_data.get("results", {})
    for component, status in results.items():
      if isinstance(status, dict):
        if "installed" in status:
          icon = "✓" if status["installed"] else "✗"
          msg = f"{component}: {icon}"
          if status.get("version"):
            msg += f" ({status['version']})"
          if status.get("error"):
            msg += f" - {status['error']}"
          print(f"  {msg}")
        elif "created" in status:
          icon = "✓" if status["created"] else "✗"
          print(f"  {component}: {icon}")
        else:
          # Nested results
          print(f"  {component}:")
          for key, value in status.items():
            if isinstance(value, list) and value:
              print(f"    {key}: {', '.join(map(str, value))}")
            elif isinstance(value, bool):
              print(f"    {key}: {'✓' if value else '✗'}")
            elif value:
              print(f"    {key}: {value}")


def main() -> int:
  """Bootstrap development environment."""
  parser = argparse.ArgumentParser(
    description="Bootstrap development environment",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=f"""
Layers:
  0 - {LAYERS[0]}
  1 - {LAYERS[1]}
  2 - {LAYERS[2]}
  3 - {LAYERS[3]}
  4 - {LAYERS[4]}

Examples:
  # Full bootstrap
  python -m helpers.bootstrap

  # Start from managed tools
  python -m helpers.bootstrap --from-layer 2

  # Only run specific layer
  python -m helpers.bootstrap --only-layer 3

  # Minimal setup (venv + deps)
  python -m helpers.bootstrap --from-layer 2 --to-layer 3
""",
  )

  # Logging options (consistent with other helpers)
  parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (can be repeated)")
  parser.add_argument("--log-file", help="Write logs to file in addition to stderr")

  # Bootstrap control
  parser.add_argument("--dry-run", action="store_true", help="Show what would be run without executing")

  # Layer selection
  parser.add_argument(
    "--from-layer", type=int, choices=[0, 1, 2, 3, 4], default=0, help="Start from layer (default: 0)"
  )
  parser.add_argument("--to-layer", type=int, choices=[0, 1, 2, 3, 4], default=4, help="Stop after layer (default: 4)")
  parser.add_argument("--only-layer", type=int, choices=[0, 1, 2, 3, 4], help="Run only specified layer")
  parser.add_argument("--skip-layer", type=int, action="append", help="Skip specific layers")

  # State management
  parser.add_argument("--input-state", type=Path, help="Load initial state from JSON file")
  parser.add_argument("--output-state", type=Path, help="Save final state to JSON file")

  # Project location
  parser.add_argument("--project-root", type=Path, help="Project root directory (default: auto-detect)")

  args = parser.parse_args()

  # Configure logging using helpers.utils
  configure_logging(args.verbose, args.log_file)

  # Determine layers to run
  if args.only_layer is not None:
    layers_to_run = [args.only_layer]
  else:
    layers_to_run = list(range(args.from_layer, args.to_layer + 1))

  # Remove skipped layers
  if args.skip_layer:
    layers_to_run = [layer for layer in layers_to_run if layer not in args.skip_layer]

  # Dry run mode
  if args.dry_run:
    print("Dry run - would execute:")
    for layer_num in layers_to_run:
      print(f"  Layer {layer_num}: {LAYERS[layer_num]}")
    return 0

  # Load initial state
  if args.input_state:
    try:
      with open(args.input_state) as f:
        state = BootstrapState.from_dict(json.load(f))
      if state.platform is None:
        state.platform = get_platform_handler()
      logger.info("Loaded initial state from %s", args.input_state)
    except Exception as e:
      logger.error("Failed to load input state: %s", e)
      return 1
  else:
    # Determine project root
    if args.project_root:
      project_root = args.project_root.resolve()
    else:
      project_root = find_project_root()

    state = BootstrapState(project_root=str(project_root))
    state.platform = get_platform_handler()
    logger.debug("Using project root: %s", project_root)

  # Execute layers
  for layer_num in layers_to_run:
    state = run_layer(layer_num, state)

    if not state.can_proceed():
      logger.error("Bootstrap failed at layer %d", layer_num)
      if args.output_state:
        with open(args.output_state, "w") as f:
          json.dump(state.to_dict(), f, indent=2)
      return 1

  # Save final state
  if args.output_state:
    try:
      with open(args.output_state, "w") as f:
        json.dump(state.to_dict(), f, indent=2)
      logger.info("Saved final state to %s", args.output_state)
    except Exception as e:
      logger.error("Failed to save output state: %s", e)

  # Display summary
  print_summary(state)
  logger.info("Bootstrap complete")
  return 0


if __name__ == "__main__":
  sys.exit(main())
