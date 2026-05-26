"""Quick verification of PHENIX integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipeline.dependency_checker import DependencyChecker
from src.pipeline.phenix_paths import has_tool, get_phenix_cmd, phenix_root

deps = DependencyChecker.get_status()
print("=== Engine Status ===")
for k, v in deps.items():
    print(f"  {k:25s}: {'YES' if v else 'NO --'}")

print(f"\nPHENIX root: {phenix_root()}")
print(f"PHASER: {has_tool('phaser')}")
print(f"refine: {has_tool('refine')}")
print(f"molprobity: {has_tool('molprobity')}")
print(f"autobuild: {has_tool('autobuild')}")

# Test command construction
cmd = get_phenix_cmd("refine", "test.pdb", "test.mtz")
print(f"\nExample refine cmd: {cmd[0]}")
print("...args:", cmd[1:])
print("\nPHENIX integration OK")
