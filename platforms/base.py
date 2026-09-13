"""Base class and data structures for Hermes Social Engagement Agent.

Defines the platform adapter interface, ContentItem, and Comment dataclasses.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContentItem:
    """Represents a piece of social content discovered on a platform."""
    platform: str
    url: str
    title: str
    description: str = ""
    transcript: str = ""
    published_date: str = ""
    creator_id: str = ""
    creator_name: str = ""
    creator_url: str = ""
    engagement_metrics: Dict[str, Any] = field(default_factory=dict)
    existing_comments: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    content_type: str = ""
    search_query: str = ""
    discovered_at: str = ""
    content_id: str = ""
    platform_content_id: str = ""


@dataclass
class Comment:
    """Represents a generated comment."""
    text: str
    strategy: str = ""
    content_item_id: str = ""
    platform: str = ""
    creator_id: str = ""
    created_at: str = ""
    quality_score: float = 0.0
    spam_risk: float = 0.0
    status: str = "generated"  # generated, approved, published, rejected
    tracking_url: str = ""
    published_at: str = ""
    published: bool = False
    draft: bool = True


class PlatformAdapter(ABC):
    """Common interface for all platform integrations."""

    def __init__(self, config: dict):
        self.config = config
        self.platform_name = self.__class__.__name__.lower().replace('adapter', '')
        self.supported_capabilities = set()
        self._initialized = False

    @abstractmethod
    def name(self) -> str:
        """Return platform name"""
        pass

    @abstractmethod
    def init(self) -> bool:
        """Initialize the platform adapter (auth, sessions, etc.)"""
        pass

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> List[ContentItem]:
        """Search for content on the platform"""
        pass

    @abstractmethod
    def get_content(self, content_id: str) -> Optional[ContentItem]:
        """Get detailed content by ID"""
        pass

    @abstractmethod
    def get_creator(self, creator_id: str) -> Optional[Dict]:
        """Get creator information"""
        pass

    @abstractmethod
    def get_comments(self, content_id: str) -> List[str]:
        """Get existing comments on content"""
        pass

    @abstractmethod
    def publish_comment(self, comment: Comment, content_item: ContentItem) -> Dict:
        """Publish a comment (or queue for approval in dry-run mode)"""
        pass

    @abstractmethod
    def get_comment_status(self, comment_id: str) -> Dict:
        """Check status of a published comment"""
        pass

    @abstractmethod
    def get_metrics(self, content_item_id: str) -> Dict:
        """Get engagement metrics for content"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the platform integration is healthy"""
        pass

    def generate_tracking_url(self, content_id: str, campaign_id: str = "") -> str:
        """Generate a UTM-tracked URL for the campaign."""
        base_url = self.config.get("WEBSITE_URL", "https://stockscribe.in")
        utm_params = {
            "utm_source": self.platform_name,
            "utm_medium": "comment",
            "utm_campaign": campaign_id or "hermes",
            "utm_content": content_id
        }
        query_string = "&".join(f"{k}={v}" for k, v in utm_params.items())
        return f"{base_url}/?{query_string}"

    def supports(self, capability: str) -> bool:
        """Check if this adapter supports a specific capability"""
        return capability in self.supported_capabilities

    def is_healthy(self) -> bool:
        """Check if the platform is available and healthy"""
        try:
            return self.health_check()
        except Exception:
            return False