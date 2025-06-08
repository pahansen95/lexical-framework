import helpers.tools.cache as hc


def test_ensure_cache_creates(tmp_path):
  cache_dir = tmp_path / "cache"
  cache_link = tmp_path / "link"
  hc.ensure_cache(cache_dir, cache_link)
  assert cache_dir.is_dir()
  assert cache_link.is_symlink()
  assert cache_link.resolve() == cache_dir


def test_ensure_cache_noop(tmp_path):
  cache_dir = tmp_path / "cache"
  cache_link = tmp_path / "link"
  cache_dir.mkdir()
  cache_link.symlink_to(cache_dir)
  hc.ensure_cache(cache_dir, cache_link)
  assert cache_link.is_symlink()
  assert cache_link.resolve() == cache_dir
