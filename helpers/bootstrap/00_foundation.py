#!/usr/bin/env python3
"""Layer 0: Foundation - Probe OS, architecture, and network connectivity."""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .state import BootstrapState
from helpers.utils import configure_logging

logger = logging.getLogger(__name__)


def probe_os_info() -> dict[str, Any]:
  """Gather operating system information."""
  return {
    "system": platform.system(),  # Linux, Darwin, Windows
    "release": platform.release(),
    "version": platform.version(),
    "machine": platform.machine(),  # x86_64, arm64, etc.
    "processor": platform.processor(),
    "platform": platform.platform(),
    "python_build": platform.python_build(),
    "python_compiler": platform.python_compiler(),
  }


def probe_network_connectivity() -> dict[str, Any]:
  """Test basic network connectivity."""
  result = {
    "dns_resolution": False,
    "https_connectivity": False,
    "package_registry": False,
    "latency_ms": None,
  }

  # Test DNS resolution
  try:
    socket.gethostbyname("pypi.org")
    result["dns_resolution"] = True
    logger.debug("DNS resolution successful")
  except socket.gaierror:
    logger.warning("DNS resolution failed")

  # Test HTTPS connectivity
  test_urls = [
    ("https://pypi.org", "package_registry"),
    ("https://github.com", "https_connectivity"),
  ]

  for url, key in test_urls:
    try:
      import urllib.request

      start_time = time.time()
      with urllib.request.urlopen(url, timeout=5) as response:
        if response.status == 200:
          result[key] = True
          if key == "https_connectivity":
            result["latency_ms"] = int((time.time() - start_time) * 1000)
      logger.debug(f"Connected to {url}")
    except Exception as e:
      logger.debug(f"Failed to connect to {url}: {e}")

  return result


def probe_filesystem() -> dict[str, Any]:
  """Probe filesystem capabilities and available space."""
  result = {
    "temp_writable": False,
    "home_writable": False,
    "cwd_writable": False,
    "disk_space_mb": None,
    "temp_dir": None,
    "home_dir": None,
  }

  # Test temp directory
  try:
    import tempfile

    temp_dir = tempfile.gettempdir()
    test_file = Path(temp_dir) / f"bootstrap_test_{os.getpid()}.tmp"
    test_file.write_text("test")
    test_file.unlink()
    result["temp_writable"] = True
    result["temp_dir"] = temp_dir
    logger.debug(f"Temp directory writable: {temp_dir}")
  except Exception:
    logger.warning("Cannot write to temp directory")

  # Test home directory
  try:
    home = Path.home()
    if home.exists():
      result["home_dir"] = str(home)
      test_file = home / f".bootstrap_test_{os.getpid()}.tmp"
      test_file.write_text("test")
      test_file.unlink()
      result["home_writable"] = True
      logger.debug(f"Home directory writable: {home}")
  except Exception:
    logger.warning("Cannot write to home directory")

  # Test current directory
  try:
    test_file = Path(f".bootstrap_test_{os.getpid()}.tmp")
    test_file.write_text("test")
    test_file.unlink()
    result["cwd_writable"] = True
    logger.debug("Current directory writable")
  except Exception:
    logger.warning("Cannot write to current directory")

  # Check disk space
  try:
    if platform.system() != "Windows":
      stat = os.statvfs(".")
      result["disk_space_mb"] = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
    else:
      import shutil

      usage = shutil.disk_usage(".")
      result["disk_space_mb"] = usage.free // (1024 * 1024)
    logger.debug(f"Available disk space: {result['disk_space_mb']} MB")
  except Exception:
    logger.warning("Cannot determine disk space")

  return result


def probe_environment_variables() -> dict[str, Any]:
  """Check relevant environment variables."""
  result = {
    "path": os.environ.get("PATH", "").split(os.pathsep),
    "shell": os.environ.get("SHELL"),
    "home": os.environ.get("HOME") or os.environ.get("USERPROFILE"),
    "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    "lang": os.environ.get("LANG"),
    "virtual_env": os.environ.get("VIRTUAL_ENV"),
    "python_path": os.environ.get("PYTHONPATH"),
  }

  # Check for CI/CD indicators
  ci_vars = ["CI", "CONTINUOUS_INTEGRATION", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"]
  result["ci_environment"] = any(os.environ.get(var) for var in ci_vars)

  return result


def verify_foundation(checks: dict[str, bool]) -> dict[str, Any]:
  """Return whether all foundation checks passed."""
  return {"foundation_ready": all(checks.values())}


def probe_system_resources() -> dict[str, Any]:
  """Probe system resource availability."""
  result = {
    "cpu_count": None,
    "memory_mb": None,
    "python_version": sys.version,
    "python_executable": sys.executable,
  }

  try:
    result["cpu_count"] = os.cpu_count()
  except Exception:
    logger.warning("Cannot determine CPU count")

  # Memory detection
  try:
    if platform.system() == "Linux":
      with open("/proc/meminfo") as f:
        for line in f:
          if line.startswith("MemTotal:"):
            kb = int(line.split()[1])
            result["memory_mb"] = kb // 1024
            break
    elif platform.system() == "Darwin":  # macOS
      output = subprocess.check_output(["sysctl", "hw.memsize"], text=True)
      bytes_mem = int(output.split(":")[1].strip())
      result["memory_mb"] = bytes_mem // (1024 * 1024)
    elif platform.system() == "Windows":
      import ctypes

      kernel32 = ctypes.windll.kernel32
      c_ulonglong = ctypes.c_ulonglong

      class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
          ("dwLength", ctypes.c_ulong),
          ("dwMemoryLoad", ctypes.c_ulong),
          ("ullTotalPhys", c_ulonglong),
          ("ullAvailPhys", c_ulonglong),
          ("ullTotalPageFile", c_ulonglong),
          ("ullAvailPageFile", c_ulonglong),
          ("ullTotalVirtual", c_ulonglong),
          ("ullAvailVirtual", c_ulonglong),
          ("ullExtendedVirtual", c_ulonglong),
        ]

      stat = MEMORYSTATUSEX()
      stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
      kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
      result["memory_mb"] = stat.ullTotalPhys // (1024 * 1024)
  except Exception as e:
    logger.warning(f"Cannot determine system memory: {e}")

  return result


def run(state: BootstrapState, *, skip_network: bool = False) -> BootstrapState:
  """Execute the foundation layer."""

  layer_results = {
    "os": probe_os_info(),
    "filesystem": probe_filesystem(),
    "environment": probe_environment_variables(),
    "resources": probe_system_resources(),
  }

  if not skip_network:
    layer_results["network"] = probe_network_connectivity()

  checks = {
    "os_supported": layer_results["os"]["system"] in ["Linux", "Darwin", "Windows"],
    "disk_space_ok": (layer_results["filesystem"]["disk_space_mb"] or 0) >= 500,
    "can_write": layer_results["filesystem"]["cwd_writable"],
    "network_ok": not skip_network and layer_results.get("network", {}).get("https_connectivity", False),
  }

  state.foundation_ready = all(checks.values())
  state.foundation_checks = checks
  state.record_verification("foundation", verify_foundation(checks))

  state.layer = 0
  state.layers.append({"layer": 0, "name": "foundation", "results": layer_results})

  return state


def main() -> None:
  """Probe foundation layer information."""
  parser = argparse.ArgumentParser(description="Layer 0: Foundation Probe")
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
  parser.add_argument("--skip-network", action="store_true", help="Skip network connectivity tests")
  args = parser.parse_args()

  configure_logging(args.verbose)
  logger.info("Starting foundation layer probe")

  # Read input state from stdin (if any)
  if not sys.stdin.isatty():
    try:
      input_state = json.load(sys.stdin)
      logger.debug("Received input state: %s", input_state)
    except json.JSONDecodeError:
      logger.warning("Failed to parse input JSON, using defaults")
      input_state = {}
  else:
    input_state = {}

  if "project_root" not in input_state:
    input_state["project_root"] = str(Path.cwd())

  state = BootstrapState.from_dict(input_state)
  state = run(state, skip_network=args.skip_network)

  # Output state to stdout
  json.dump(state.to_dict(), sys.stdout, indent=2)
  print()  # Newline for readability

  if state.foundation_ready:
    logger.info("Foundation layer probe complete - environment suitable")
  else:
    logger.warning("Foundation layer probe complete - issues detected")
    for check, passed in state.foundation_checks.items():
      if not passed:
        logger.warning(f"  Failed: {check}")


if __name__ == "__main__":
  main()
