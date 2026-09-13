#!/usr/bin/env python3
"""Hermes Social CLI (minimal version)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from database import Database
from logger import Logger


def main():
    parser = argparse.ArgumentParser(prog="hermes-social", description="Hermes Social Engagement Agent")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    parser.add_argument("--discover", action="store_true", help="Run discovery phase (stub)")
    args = parser.parse_args()

    cfg = Config()
    db = Database()
    logger = Logger()

    if args.status:
        # Show basic info from config and DB
        campaigns = db.select("SELECT count(*) as c FROM campaigns")
        platforms_row = db.select("SELECT count(*) as c FROM platforms")
        comments_row = db.select("SELECT count(*) as c FROM comments")
        print(f"DRY_RUN: {cfg.is_dry_run()}")
        print(f"APPROVAL_REQUIRED: {cfg.is_approval_required()}")
        print(f"AUTONOMOUS: {cfg.is_autonomous()}")
        print(f"DB_PATH: {db.db_path}")
        print(f"CAMPAIGNS: {campaigns[0][0] if campaigns else 0}")
        print(f"PLATFORMS: {platforms_row[0][0] if platforms_row else 0}")
        print(f"COMMENTS: {comments_row[0][0] if comments_row else 0}")
        print(f"YOUTUBE_ENABLED: {cfg.is_platform_enabled('youtube')}")
    elif args.discover:
        # Run a stub discovery phase
        print("Discovery stub: check config for enabled platforms")
        print(f"YouTube enabled: {cfg.is_platform_enabled('youtube')}")
        print(f"Instagram enabled: {cfg.is_platform_enabled('instagram')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
