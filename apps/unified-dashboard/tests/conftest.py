import sys
from pathlib import Path
import importlib.util

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Map apps.unified_dashboard to apps/unified-dashboard
ud_path = Path(__file__).resolve().parent.parent
if str(ud_path) not in sys.path:
    sys.path.insert(0, str(ud_path))

# Dynamic module registration
if "apps.unified_dashboard" not in sys.modules:
    ud_spec = importlib.util.spec_from_file_location("apps.unified_dashboard", ud_path / "__init__.py")
    ud_mod = importlib.util.module_from_spec(ud_spec)
    ud_mod.__path__ = [str(ud_path)]
    sys.modules["apps.unified_dashboard"] = ud_mod
