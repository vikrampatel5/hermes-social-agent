#!/usr/bin/env python3
"""hermes_social entry point for: python -m hermes_social"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cli_social import main
if __name__ == "__main__":
    main()
