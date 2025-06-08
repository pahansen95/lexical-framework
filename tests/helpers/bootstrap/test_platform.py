from helpers.bootstrap.platform import get_platform_handler, LinuxPlatform, MacOSPlatform, WindowsPlatform
import platform


def test_get_platform_handler(monkeypatch):
  monkeypatch.setattr(platform, "system", lambda: "Linux")
  assert isinstance(get_platform_handler(), LinuxPlatform)
  monkeypatch.setattr(platform, "system", lambda: "Darwin")
  assert isinstance(get_platform_handler(), MacOSPlatform)
  monkeypatch.setattr(platform, "system", lambda: "Windows")
  assert isinstance(get_platform_handler(), WindowsPlatform)
