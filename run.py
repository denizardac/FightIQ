#!/usr/bin/env python3
"""
🥊 FIGHTIQ LAUNCHER
Run from project root to start the system
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Run main from core
from core.main import main

if __name__ == "__main__":
    main()
