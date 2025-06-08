from helpers.tools import build, cache, docs, format as fmt, lint, python, test as htest


def test_venv_want_constants() -> None:
  assert build.VENV_WANT == "dev"
  assert cache.VENV_WANT == "dev"
  assert docs.VENV_WANT == "docs"
  assert fmt.VENV_WANT == "dev"
  assert lint.VENV_WANT == "dev"
  assert htest.VENV_WANT == "test"
  assert python.VENV_WANT == "dev"

