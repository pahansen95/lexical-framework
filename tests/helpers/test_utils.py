import sys

from helpers.utils import run_command, check_command_exists


def test_run_command_logs_python(caplog):
  caplog.set_level("INFO")
  result = run_command([sys.executable, "-c", 'print("ok")'], capture_output=True, text=True)
  assert result.stdout.strip() == "ok"
  assert caplog.records
  assert caplog.records[0].message.startswith("$ python")


def test_check_command_exists():
  assert check_command_exists("python")
  assert not check_command_exists("unlikely_cmd_xyz")
