"""Guide for setting up the conda environment for X-ray crystallography pipeline."""
import subprocess
import sys
from pathlib import Path


ENV_YML = Path(__file__).parent.parent / "environment.yml"


def main():
    print("X-ray Crystallography Pipeline — Environment Setup")
    print("=" * 50)

    if not ENV_YML.exists():
        print(f"ERROR: {ENV_YML} not found")
        sys.exit(1)

    print(f"\nCreating conda environment from: {ENV_YML}")
    print("\nThis installs DIALS, CCTBX, and all Python dependencies.\n")

    result = subprocess.run(
        ["conda", "env", "create", "-f", str(ENV_YML)],
        capture_output=False,
    )

    if result.returncode == 0:
        print("\nEnvironment created successfully.")
        print("Activate with: conda activate xray-crystallography")
        print("Then run: python scripts/check_dependencies.py")
    else:
        print("\nEnvironment creation failed. Check conda installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
