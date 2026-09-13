"""Configuration loader for the Hermes social engagement agent.

Reads from environment variables and an optional .env file. All defaults
are conservative and safe for dry-run mode.
"""

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass


class Config:
    def __init__(self, env_path: str = None):
        self.config = {}
        self.env_path = env_path or os.environ.get("HERMES_SOCIAL_ENV", ".env")
        env_file = Path(self.env_path)
        if env_file.exists():
            load_dotenv(env_file)
        self._load()

    def _load(self):
        self.config = {
            "APP_ENV": os.getenv("APP_ENV", "development"),
            "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///data/state.db"),
            "REDIS_URL": os.getenv("REDIS_URL", ""),
            "AUTONOMOUS_POSTING_ENABLED": os.getenv("AUTONOMOUS_POSTING_ENABLED", "false").lower() == "true",
            "APPROVAL_REQUIRED": os.getenv("APPROVAL_REQUIRED", "true").lower() == "true",
            "MIN_RELEVANCE_SCORE": float(os.getenv("MIN_RELEVANCE_SCORE", "75")),
            "MIN_COMMENT_VALUE_SCORE": float(os.getenv("MIN_COMMENT_VALUE_SCORE", "70")),
            "MAX_SPAM_RISK_SCORE": float(os.getenv("MAX_SPAM_RISK_SCORE", "20")),
            "MAX_COMMENTS_PER_HOUR": int(os.getenv("MAX_COMMENTS_PER_HOUR", "5")),
            "MAX_COMMENTS_PER_DAY": int(os.getenv("MAX_COMMENTS_PER_DAY", "20")),
            "CREATOR_COOLDOWN_HOURS": int(os.getenv("CREATOR_COOLDOWN_HOURS", "48")),
            "CONTENT_COOLDOWN_HOURS": int(os.getenv("CONTENT_COOLDOWN_HOURS", "24")),
            "DISCOVERY_INTERVAL_MINUTES": int(os.getenv("DISCOVERY_INTERVAL_MINUTES", "60")),
            "ANALYSIS_INTERVAL_MINUTES": int(os.getenv("ANALYSIS_INTERVAL_MINUTES", "30")),
            "METRICS_INTERVAL_MINUTES": int(os.getenv("METRICS_INTERVAL_MINUTES", "30")),
            "LEARNING_INTERVAL_HOURS": int(os.getenv("LEARNING_INTERVAL_HOURS", "6")),
            "YOUTUBE_ENABLED": os.getenv("YOUTUBE_ENABLED", "true").lower() == "true",
            "INSTAGRAM_ENABLED": os.getenv("INSTAGRAM_ENABLED", "true").lower() == "true",
            "X_ENABLED": os.getenv("X_ENABLED", "false").lower() == "true",
            "REDDIT_ENABLED": os.getenv("REDDIT_ENABLED", "false").lower() == "true",
            "LINKEDIN_ENABLED": os.getenv("LINKEDIN_ENABLED", "false").lower() == "true",
            "DRY_RUN": os.getenv("DRY_RUN", "true").lower() == "true",
            "GLOBAL_KILL_SWITCH": os.getenv("GLOBAL_KILL_SWITCH", "false").lower() == "true",
            "PLATFORM_KILL_SWITCH": os.getenv("PLATFORM_KILL_SWITCH", "false").lower() == "true",
            "CAMPAIGN_KILL_SWITCH": os.getenv("CAMPAIGN_KILL_SWITCH", "false").lower() == "true",
            "ACCOUNT_KILL_SWITCH": os.getenv("ACCOUNT_KILL_SWITCH", "false").lower() == "true",
            "WEBSITE_URL": os.getenv("WEBSITE_URL", "https://stockscribe.in"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "EXPLORATION_RATE": float(os.getenv("EXPLORATION_RATE", "0.1")),
            "EXPLOITATION_RATE": float(os.getenv("EXPLOITATION_RATE", "0.7")),
            "TEST_RATE": float(os.getenv("TEST_RATE", "0.2")),
            "DUPLICATE_SIMILARITY_THRESHOLD": float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85")),
            "CREATOR_QUALITY_MIN": float(os.getenv("CREATOR_QUALITY_MIN", "50")),
            "STRATEGY_WEIGHTS": json.loads(os.getenv(
                "STRATEGY_WEIGHTS",
                '{"technical": 0.3, "educational": 0.25, "question": 0.15, "tool_mention": 0.1, "promotional": 0.05, "no_cta": 0.15}'
            )),
        }

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value

    def all(self) -> dict:
        return self.config.copy()

    def update(self, config_dict: dict):
        self.config.update(config_dict)

    def is_platform_enabled(self, platform: str) -> bool:
        key = f"{platform.upper()}_ENABLED"
        return self.config.get(key, False)

    def is_autonomous(self) -> bool:
        return self.config.get("AUTONOMOUS_POSTING_ENABLED", False) and not self.config.get("GLOBAL_KILL_SWITCH", False)

    def is_approval_required(self) -> bool:
        return self.config.get("APPROVAL_REQUIRED", True)

    def is_dry_run(self) -> bool:
        return self.config.get("DRY_RUN", True)

    def is_kill_switch_active(self) -> bool:
        return any([
            self.config.get("GLOBAL_KILL_SWITCH", False),
            self.config.get("PLATFORM_KILL_SWITCH", False),
            self.config.get("CAMPAIGN_KILL_SWITCH", False),
            self.config.get("ACCOUNT_KILL_SWITCH", False)
        ])

    def to_dict(self) -> dict:
        return self.config.copy()