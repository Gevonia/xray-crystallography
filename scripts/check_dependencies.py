"""Check which crystallography engines are available in the current environment."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipeline.dependency_checker import DependencyChecker


def main():
    status = DependencyChecker.get_status()
    print(json.dumps(status, indent=2))
    all_ok = all(status.values())
    if all_ok:
        print("\nAll engines available.")
    else:
        missing = [k for k, v in status.items() if not v]
        print(f"\nMissing engines: {', '.join(missing)}")
        print("Run 'conda env create -f environment.yml' to install dependencies.")


if __name__ == "__main__":
    main()
