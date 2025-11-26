"""
Quick test script for Modern UI
Run this to test the UI without running the full agent
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.modern_ui import run

if __name__ == "__main__":
    print("=" * 50)
    print("Testing Modern Dark UI")
    print("=" * 50)
    print("\nFeatures:")
    print("  [OK] Fixed dark theme")
    print("  [OK] Consistent colors")
    print("  [OK] High contrast text")
    print("  [OK] Professional look")
    print("\nLaunching...\n")

    run()
