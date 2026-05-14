"""
Quick import test for all FightIQ modules.
Run with: python tools/test_imports.py
"""
import sys
import os
import importlib.util

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
sys.path.insert(0, PROJECT_ROOT)

modules = sorted([
    f for f in os.listdir(MODULES_DIR)
    if f.endswith(".py") and not f.startswith("__")
])

results = {"ok": [], "fail": []}

for mod_file in modules:
    mod_path = os.path.join(MODULES_DIR, mod_file)
    spec = importlib.util.spec_from_file_location(mod_file[:-3], mod_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        results["ok"].append(mod_file)
        print(f"  ✅ {mod_file}")
    except Exception as e:
        results["fail"].append((mod_file, str(e)))
        print(f"  ❌ {mod_file}: {e}")

print("\n" + "="*50)
print(f"RESULT: {len(results['ok'])}/{len(modules)} modules import clean")
if results["fail"]:
    print("\nFAILED MODULES:")
    for name, err in results["fail"]:
        print(f"  - {name}: {err}")
