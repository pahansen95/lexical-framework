import argparse
import logging

from helpers.utils import add_logging_args, configure_logging


def test_add_logging_args(tmp_path):
  parser = argparse.ArgumentParser()
  add_logging_args(parser)
  log_file = tmp_path / "out.log"
  args = parser.parse_args(["-vv", "--log-file", str(log_file)])
  assert args.verbose == 2
  assert args.log_file == str(log_file)


def test_configure_logging(tmp_path):
  log_file = tmp_path / "log.txt"
  configure_logging(1, str(log_file))
  logger = logging.getLogger(__name__)
  logger.info("hello")
  for handler in logger.handlers:
    handler.flush()
  assert logging.getLogger().level == logging.INFO
  assert "hello" in log_file.read_text()
