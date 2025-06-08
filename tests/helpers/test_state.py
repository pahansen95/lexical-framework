from helpers.bootstrap.state import BootstrapState


def test_from_dict_filters_unknown_fields():
  data = {"project_root": "/tmp/project", "layer": 1, "unknown": "ignore"}
  state = BootstrapState.from_dict(data)
  assert state.project_root == "/tmp/project"
  assert state.layer == 1
  assert not hasattr(state, "unknown")


def test_to_dict_roundtrip():
  state = BootstrapState(project_root="/tmp")
  state.warnings.append("warn")
  d = state.to_dict()
  assert d["project_root"] == "/tmp"
  assert d["warnings"] == ["warn"]


def test_can_proceed():
  state = BootstrapState(project_root="/tmp")
  assert state.can_proceed()
  state.errors.append("failure")
  assert not state.can_proceed()


def test_record_decision():
  state = BootstrapState(project_root="/tmp")
  state.record_decision("python", "use_existing")
  assert state.decisions["python"] == "use_existing"


def test_record_verification():
  state = BootstrapState(project_root="/tmp")
  state.record_verification("python", {"installed": True})
  assert state.verifications["python"]["installed"]
