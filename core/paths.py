# FightIQ Paths - Centralized Path Resolution
import os

# Project root detection
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# Try to find project root by looking for key files
if os.path.exists(os.path.join(_FILE_DIR, "..", "core")):
    # We're in /modules
    PROJECT_ROOT = os.path.dirname(_FILE_DIR)
elif os.path.exists(os.path.join(_FILE_DIR, "core")):
    # We're in project root
    PROJECT_ROOT = _FILE_DIR
else:
    # Fallback to parent
    PROJECT_ROOT = os.path.dirname(_FILE_DIR)

# Directory paths
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
VISUALS_DIR = os.path.join(OUTPUT_DIR, "visuals")

_LEGACY_WARNED = set()


def get_data_path(filename):
    """Get path to data file with fallback to root"""
    # Try new location first
    new_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(new_path):
        return new_path

    # Fallback to root (legacy compatibility) — warn loudly: a leftover root
    # file can silently feed STALE data into the pipeline.
    root_path = os.path.join(PROJECT_ROOT, filename)
    if os.path.exists(root_path):
        if filename not in _LEGACY_WARNED:
            _LEGACY_WARNED.add(filename)
            print(f"⚠️ LEGACY PATH: reading '{filename}' from project root instead of data/. "
                  f"Move it to data/ — root copies can be stale.")
        return root_path

    # Return new path for creation
    return new_path

def get_output_path(filename, subdir="visuals"):
    """Get path for output file"""
    out_dir = os.path.join(OUTPUT_DIR, subdir)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, filename)

# For legacy compatibility when imported
DB_FILE = get_data_path("fighters_db.json")

# Explicit re-export for modules that need absolute paths (fonts, .env, etc.)
__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "MODULES_DIR",
    "ASSETS_DIR",
    "OUTPUT_DIR",
    "VISUALS_DIR",
    "get_data_path",
    "get_output_path",
    "DB_FILE",
]
