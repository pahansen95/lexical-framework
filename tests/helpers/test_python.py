from pathlib import Path

import pytest

import helpers.tools.python as hp


def test_resolve_venv_path_default():
  assert hp.resolve_venv_path("default") == Path(".venv")


def test_resolve_venv_path_named():
  assert hp.resolve_venv_path("foo") == Path(".venv") / "foo"


def test_ensure_venv_exists(monkeypatch, tmp_path):
  monkeypatch.setattr(hp, "BASE_VENV_DIR", tmp_path / ".venv")
  existing = hp.BASE_VENV_DIR / "foo"
  existing.mkdir(parents=True)
  assert hp.ensure_venv_exists("foo") == existing
  with pytest.raises(SystemExit):
    hp.ensure_venv_exists("bar")
