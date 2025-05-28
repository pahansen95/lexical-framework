import pathlib
import sys

PROJ_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, (PROJ_ROOT / "src").as_posix())
