"""Hermes Social Engagement Agent - Main Orchestration Module.

This module implements the core pipeline for the Hermes social engagement agent:
Discovery -> Analysis -> Comment Generation -> Quality Check -> Queue -> Publishing -> Tracking -> Learning.

It is designed to be extensible and safe, with dry-run mode as default.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from logger import Logger
from config import Config
from database import Database
from platforms.base import PlatformAdapter, ContentItem, Comment
from platforms.youtube_adapter import YouTubeAdapter

try:
    from platforms.instagram_adapter import InstagramAdapter
except ImportError:
    InstagramAdapter = None
try:
    from platforms.x_adapter import XAdapter
except ImportError:
    XAdapter = None
try:
    from platforms.reddit_adapter import RedditAdapter
except ImportError:
    RedditAdapter = None
try:
    from platforms.linkedin_adapter import LinkedInAdapter
except ImportError:
    LinkedInAdapter = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HermesSocialAgent:
    """Main orchestrator for the Hermes social engagement agent."""

    def __init__(self, config_path: str = ".env"):
        self.logger = Logger()
        self.config = Config(config_path)
        self.db = Database(self.config.get("DATABASE_URL", "data/state.db"))
        self.platforms: Dict[str, PlatformAdapter] = {}
        self.running = False
        self.initialized = False

    async def initialize(self):
        """Initialize the agent and all enabled platforms."""
        if self.initialized:
            return

        self.logger.info("HERMES_SOCIAL_AGENT_INIT", version="1.0.0")

        # Initialize platform adapters
        platform_classes = {
            "youtube": YouTubeAdapter,
            "instagram": InstagramAdapter,
            "x": XAdapter,
            "reddit": RedditAdapter,
            "linkedin": LinkedInAdapter,
        }
        # Filter out None values for missing adapters
        platform_classes = {k: v for k, v in platform_classes.items() if v is not None}

        for platform_name, adapter_class in platform_classes.items():
            if self.config.is_platform_enabled(platform_name):
                try:
                    adapter = adapter_class(self.config.all())
                    if adapter.init():
                        self.platforms[platform_name] = adapter
                        self.logger.info("PLATFORM_INITIALIZED", platform=platform_name)
                    else:
                        self.logger.warning("PLATFORM_INIT_FAILED", platform=platform_name)
                except Exception as e:
                    self.logger.error("PLATFORM_INIT_ERROR", platform=platform_name, error=str(e))

        self.initialized = True
        self.logger.info("AGENT_INITIALIZATION_COMPLETE", platforms=list(self.platforms.keys()))

    async def start(self):
        """Start the agent pipeline."""
        if self.running:
            self.logger.warning("AGENT_ALREADY_RUNNING")
            return

        await self.initialize()
        self.running = True
        self.logger.info("AGENT_STARTING")

        # Start the main orchestration loop
        await self._orchestration_loop()

    async def _orchestration_loop(self):
        """Main orchestration loop."""
        while self.running:
            try:
                # Check global kill switch
                if self.config.is_kill_switch_active():
                    self.logger.warning("KILL_SWITCH_ACTIVE")
                    await asyncio.sleep(60)
                    continue

                # Execute one full cycle
                await self._execution_cycle()

                # Wait for next cycle based on discovery interval
                await asyncio.sleep(self.config.get("DISCOVERY_INTERVAL_MINUTES", 60) * 60)

            except Exception as e:
                self.logger.error("ORCHESTRATION_ERROR", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _execution_cycle(self):
        """Execute one full pipeline cycle."""
        self.logger.info("EXECUTION_CYCLE_START")

        # 1. Discovery: Find relevant content
        discovered_content = await self._discovery_phase()
        self.logger.info("DISCOVERY_COMPLETE", count=len(discovered_content))

        # 2. Analysis: Score and filter content
        analyzed_content = await self._analysis_phase(discovered_content)
        self.logger.info("ANALYSIS_COMPLETE", total=len(discovered_content), qualified=len(analyzed_content))

        # 3. Comment Generation: Generate comments for qualified content
        generated_comments = await self._comment_generation_phase(analyzed_content)
        self.logger.info("COMMENT_GENERATION_COMPLETE", count=len(generated_comments))

        # 4. Quality Check: Evaluate generated comments
        qualified_comments = await self._quality_check_phase(generated_comments)
        self.logger.info("QUALITY_CHECK_COMPLETE", total=len(generated_comments), qualified=len(qualified_comments))

        # 5. Queue: Save qualified comments to database
        await self._queue_phase(qualified_comments)
        self.logger.info("QUEUE_COMPLETE", count=len(qualified_comments))

        # 6. Publishing: Publish approved comments (if not dry-run)
        if not self.config.is_dry_run() and self.config.is_autonomous():
            await self._publishing_phase(qualified_comments)
            self.logger.info("PUBLISHING_COMPLETE")
        else:
            self.logger.info("PUBLISHING_SKIPPED", dry_run=self.config.is_dry_run(), autonomous=self.config.is_autonomous())

        # 7. Tracking: Collect website analytics (stub)
        await self._tracking_phase()
        self.logger.info("TRACKING_COMPLETE")

        # 8. Learning: Analyze performance and update strategies (stub)
        await self._learning_phase()
        self.logger.info("LEARNING_COMPLETE")

        self.logger.info("EXECUTION_CYCLE_COMPLETE")

    async def _discovery_phase(self) -> List[ContentItem]:
        """Discover relevant content across all enabled platforms."""
        discovered_content = []

        # Get search queries from config (could be loaded from database)
        queries = self._get_search_queries()

        for platform_name, adapter in self.platforms.items():
            if not adapter.is_healthy():
                self.logger.warning("PLATFORM_UNHEALTHY", platform=platform_name)
                continue

            for query in queries:
                try:
                    # Search for content
                    content_items = await adapter.search(query, max_results=10)
                    discovered_content.extend(content_items)
                    self.logger.info("PLATFORM_DISCOVERY", platform=platform_name, query=query, results=len(content_items))
                except Exception as e:
                    self.logger.error("PLATFORM_DISCOVERY_ERROR", platform=platform_name, query=query, error=str(e))

        # Deduplicate content by URL and platform
        seen = set()
        unique_content = []
        for content in discovered_content:
            key = (content.platform, content.url)
            if key not in seen:
                seen.add(key)
                unique_content.append(content)

        return unique_content

    def _get_search_queries(self) -> List[str]:
        """Get search queries from configuration or database."""
        # For now, return a default list of investing/trading queries
        # In a full implementation, these would be configurable per platform and stored in database
        return [
            "stock screening",
            "stock analysis",
            "stock research",
            "how to analyze stocks",
            "how to find good stocks",
            "stock valuation",
            "portfolio analysis",
            "fundamental analysis",
            "technical analysis",
            "Indian stocks",
            "NIFTY",
            "NSE",
            "BSE",
            "IPO",
            "mutual funds",
            "ETFs",
            "dividend investing",
            "value investing",
            "growth stocks",
        ]

    async def _analysis_phase(self, content_items: List[ContentItem]) -> List[Dict[str, Any]]:
        """Analyze and score content items."""
        analyzed = []

        for content in content_items:
            try:
                # Calculate various scores
                relevance_score = await self._calculate_relevance_score(content)
                stockscribe_fit_score = await self._calculate_stockscribe_fit(content)
                audience_fit_score = await self._calculate_audience_fit(content)
                comment_value_score = await self._calculate_comment_value(content)
                spam_risk_score = await self._calculate_spam_risk(content)
                conversion_potential_score = await self._calculate_conversion_potential(content)
                creator_quality_score = await self._calculate_creator_quality_score(content)
                overall_score = await self._calculate_overall_score({
                    "relevance": relevance_score,
                    "stockscribe_fit": stockscribe_fit_score,
                    "audience_fit": audience_fit_score,
                    "comment_value": comment_value_score,
                    "spam_risk": spam_risk_score,
                    "conversion_potential": conversion_potential_score,
                    "creator_quality": creator_quality_score,
                })

                # Determine if content is suitable for commenting
                decision = self._make_content_decision({
                    "relevance_score": relevance_score,
                    "stockscribe_fit_score": stockscribe_fit_score,
                    "audience_fit_score": audience_fit_score,
                    "comment_value_score": comment_value_score,
                    "spam_risk_score": spam_risk_score,
                    "conversion_potential_score": conversion_potential_score,
                    "creator_quality_score": creator_quality_score,
                    "overall_score": overall_score,
                })

                # Store analysis in database (optional, for tracking)
                await self._store_content_analysis(content, {
                    "relevance_score": relevance_score,
                    "stockscribe_fit_score": stockscribe_fit_score,
                    "audience_fit_score": audience_fit_score,
                    "comment_value_score": comment_value_score,
                    "spam_risk_score": spam_risk_score,
                    "conversion_potential_score": conversion_potential_score,
                    "creator_quality_score": creator_quality_score,
                    "overall_score": overall_score,
                    "decision": decision,
                })

                analyzed.append({
                    "content": content,
                    "scores": {
                        "relevance_score": relevance_score,
                        "stockscribe_fit_score": stockscribe_fit_score,
                        "audience_fit_score": audience_fit_score,
                        "comment_value_score": comment_value_score,
                        "spam_risk_score": spam_risk_score,
                        "conversion_potential_score": conversion_potential_score,
                        "creator_quality_score": creator_quality_score,
                        "overall_score": overall_score,
                    },
                    "decision": decision,
                })

                self.logger.info("CONTENT_ANALYZED", 
                                url=content.url[:50],
                                relevance=int(relevance_score),
                                fit=int(stockscribe_fit_score),
                                spam_risk=int(spam_risk_score),
                                decision=decision)

            except Exception as e:
                self.logger.error("CONTENT_ANALYSIS_ERROR", url=content.url, error=str(e))

        # Filter by relevance thresholds
        min_relevance = self.config.get("MIN_RELEVANCE_SCORE", 75)
        max_spam_risk = self.config.get("MAX_SPAM_RISK_SCORE", 20)
        qualified = [
            item for item in analyzed
            if item["scores"]["overall_score"] >= min_relevance
            and item["scores"]["spam_risk_score"] <= max_spam_risk
        ]

        return qualified

    async def _comment_generation_phase(self, analyzed_content: List[Dict[str, Any]]) -> List[Comment]:
        """Generate comments for analyzed content."""
        comments = []

        # Get campaign instructions
        campaign_instructions = await self._get_campaign_instructions()

        for item in analyzed_content:
            try:
                content = item["content"]
                scores = item["scores"]

                # Generate comment
                comment_text = await self._generate_contextual_comment(content, scores, campaign_instructions)
                if not comment_text:
                    continue

                # Create comment object
                comment = Comment(
                    text=comment_text,
                    strategy="contextual",
                    content_item_id=content.content_id,
                    platform=content.platform,
                    creator_id=content.creator_id,
                    created_at=datetime.utcnow().isoformat(),
                    quality_score=scores["comment_value_score"],
                    spam_risk=scores["spam_risk_score"],
                    status="generated",
                    tracking_url="",  # Will be set when publishing
                    published_at="",
                    published=False,
                    draft=True,
                )

                comments.append(comment)
                self.logger.info("COMMENT_GENERATED", 
                                url=content.url[:50],
                                length=len(comment_text),
                                quality_score=comment.quality_score,
                                spam_risk=comment.spam_risk)

            except Exception as e:
                self.logger.error("COMMENT_GENERATION_ERROR", url=content.url, error=str(e))

        return comments

    async def _quality_check_phase(self, comments: List[Comment]) -> List[Comment]:
        """Perform quality check on generated comments."""
        qualified = []

        for comment in comments:
            try:
                quality_result = await self._quality_check(comment)
                if quality_result["score"] >= self.config.get("MIN_COMMENT_VALUE_SCORE", 70):
                    qualified.append(comment)
                    self.logger.info("COMMENT_QUALIFIED", 
                                    comment_id="generated",
                                    quality_score=int(quality_result["score"]),
                                    passes_quality=quality_result["passes_quality"])
                else:
                    self.logger.info("COMMENT_REJECTED_QUALITY", 
                                    comment_id="generated",
                                    quality_score=int(quality_result["score"]),
                                    reason="below_threshold")
            except Exception as e:
                self.logger.error("QUALITY_CHECK_ERROR", comment_id="generated", error=str(e))

        return qualified

    async def _queue_phase(self, comments: List[Comment]):
        """Save comments to the queue database."""
        for comment in comments:
            try:
                # Store comment in database
                comment_id = await self._store_comment(comment)
                self.logger.info("COMMENT_QUEUED", comment_id=comment_id)
            except Exception as e:
                self.logger.error("QUEUE_ERROR", comment_id="generated", error=str(e))

    async def _publishing_phase(self, comments: List[Comment]):
        """Publish approved comments."""
        for comment in comments:
            try:
                # Get platform adapter
                platform_name = comment.platform
                if platform_name not in self.platforms:
                    self.logger.error("PLATFORM_NOT_AVAILABLE", platform=platform_name)
                    continue

                platform = self.platforms[platform_name]

                # Get content item
                content_analysis = await self._get_content_analysis(comment.content_item_id)
                if not content_analysis:
                    self.logger.error("CONTENT_NOT_FOUND", content_id=comment.content_item_id)
                    continue

                content = content_analysis["content"]

                # Publish comment
                publish_result = await platform.publish_comment(comment, content)

                if publish_result["status"] == "success":
                    # Update comment as published
                    await self._update_comment_published(comment.content_item_id, True, publish_result.get("comment_id"))
                    self.logger.info("COMMENT_PUBLISHED", 
                                    platform=platform_name,
                                    content_url=content.url[:50])
                else:
                    self.logger.error("COMMENT_PUBLISH_FAILED", 
                                    platform=platform_name,
                                    error=publish_result.get("error", "unknown"))

            except Exception as e:
                self.logger.error("PUBLISHING_ERROR", comment_id="generated", error=str(e))

    async def _tracking_phase(self):
        """Collect website analytics (stub)."""
        # In a full implementation, this would integrate with website analytics
        # to track clicks, signups, etc. from UTM parameters.
        self.logger.info("TRACKING_PHASE_STUB")

    async def _learning_phase(self):
        """Analyze performance and update strategies (stub)."""
        # In a full implementation, this would analyze comment performance
        # and update strategy weights, query priorities, etc.
        self.logger.info("LEARNING_PHASE_STUB")

    # Helper methods for scoring and decision making

    async def _calculate_relevance_score(self, content: ContentItem) -> float:
        """Calculate content relevance score based on keywords and topics."""
        score = 30.0  # Base score
        text = (content.title + " " + content.description + " " + content.transcript).lower()
        
        # Investing/trading keywords
        keywords = {
            "stock": 10,
            "share": 10,
            "equity": 10,
            "invest": 15,
            "investment": 15,
            "trade": 10,
            "trading": 10,
            "market": 10,
            "portfolio": 10,
            "dividend": 10,
            "etf": 10,
            "ipo": 10,
            "nifty": 10,
            "sensex": 10,
            "bse": 10,
            "nse": 10,
            "valuation": 10,
            "fundamental": 10,
            "technical": 10,
            "analysis": 10,
            "research": 10,
            "screen": 10,
            "screening": 10,
            "buy": 5,
            "sell": 5,
            "hold": 5,
            "target price": 10,
            "eps": 5,
            "pe ratio": 10,
            "pb ratio": 10,
            "roe": 10,
            "roce": 10,
            "debt to equity": 10,
            "current ratio": 10,
            "profit margin": 10,
            "revenue": 10,
            "earnings": 10,
            "quarterly": 5,
            "annual": 5,
            "fy": 5,
            "q1": 5,
            "q2": 5,
            "q3": 5,
            "q4": 5,
        }

        for keyword, weight in keywords.items():
            if keyword in text:
                score += weight

        # Boost for multiple keywords
        keyword_count = sum(1 for k in keywords if k in text)
        if keyword_count >= 3:
            score += 10
        if keyword_count >= 5:
            score += 15
        if keyword_count >= 7:
            score += 20

        return min(score, 100.0)

    async def _calculate_stockscribe_fit(self, content: ContentItem) -> float:
        """Calculate how well the content fits StockScribe's audience and mission."""
        score = 40.0  # Base score
        text = (content.title + " " + content.description).lower()
        
        # StockScribe specific fit
        if "stock research" in text:
            score += 25
        if "stock screener" in text:
            score += 25
        if "portfolio analysis" in text:
            score += 20
        if "fundamental analysis" in text:
            score += 20
        if "technical analysis" in text:
            score += 15
        if "valuation" in text:
            score += 15
        if "dividend" in text:
            score += 10
        if "etf" in text:
            score += 10
        if "mutual fund" in text:
            score += 10
        if "ipo" in text:
            score += 10
        if "nifty" in text:
            score += 10
        if "sensex" in text:
            score += 10
        if "bse" in text:
            score += 10
        if "nse" in text:
            score += 10

        # Penalty for overly speculative or gambling-like content
        if "guaranteed return" in text or "sure shot" in text or "100% profit" in text:
            score -= 30
        if "penny stock" in text and "multibagger" in text:
            score -= 15

        return max(min(score, 100.0), 0.0)

    async def _calculate_audience_fit(self, content: ContentItem) -> float:
        """Calculate how well the content fits the target audience."""
        score = 50.0  # Base score
        text = (content.title + " " + content.description).lower()
        
        # Audience characteristics: retail investors in India
        if "beginner" in text or "new investor" in text:
            score += 15
        if "guide" in text or "tutorial" in text or "how to" in text:
            score += 15
        if "step by step" in text:
            score += 10
        if "for dummies" in text or "idiot's guide" in text:
            score += 10
        if "indian market" in text or "india" in text:
            score += 10
        if "retail investor" in text:
            score += 15
        if "individual investor" in text:
            score += 10
        if "demo" in text or "free trial" in text:
            score += 10
        if "webinar" in text or "live session" in text:
            score += 5

        # Penalty for overly advanced or institutional content
        if "institutional investor" in text or "hedge fund" in text or "proprietary trading" in text:
            score -= 15
        if "algorithmic trading" in text or "quantitative" in text:
            score -= 10
        if "derivatives" in text or "futures and options" in text:
            score -= 10
        if "intraday" in text and "leverage" in text:
            score -= 15

        return max(min(score, 100.0), 0.0)

    async def _calculate_comment_value(self, content: ContentItem) -> float:
        """Calculate the potential value of a comment on this content."""
        score = 40.0  # Base score
        text = (content.title + " " + content.description).lower()
        
        # Characteristics that make a comment valuable
        if "analysis" in text:
            score += 15
        if "insight" in text:
            score += 15
        if "perspective" in text:
            score += 10
        if "experience" in text:
            score += 10
        if "lesson" in text:
            score += 10
        if "tip" in text:
            score += 10
        if "strategy" in text:
            score += 10
        if "lesson learned" in text:
            score += 15
        if "mistake" in text:
            score += 10
        if "what i learned" in text:
            score += 15
        if "my approach" in text:
            score += 10
        if "framework" in text:
            score += 10
        if "checklist" in text:
            score += 10
        if "dos and don'ts" in text:
            score += 10

        # Boost for actionable content
        if "you should" in text or "consider" in text or "try" in text:
            score += 10
        if "actionable" in text or "practical" in text:
            score += 15

        return max(min(score, 100.0), 0.0)

    async def _calculate_spam_risk(self, content: ContentItem) -> float:
        """Calculate spam risk score."""
        score = 0.0  # Base spam risk
        text = (content.title + " " + content.description).lower()
        
        # Spam indicators
        spam_indicators = {
            "click here": 20,
            "buy now": 15,
            "limited time": 15,
            "act now": 15,
            "don't miss": 15,
            "exclusive offer": 20,
            "special promotion": 20,
            "free trial": 10,  # Could be legitimate but often used in spam
            "guaranteed": 20,
            "risk free": 20,
            "no loss": 20,
            "100% profit": 25,
            "double your money": 25,
            "multibagger": 15,
            "sure shot": 20,
            "hot tip": 15,
            "stock tip": 15,
            "recommendation": 10,
            "buy this stock": 15,
            "sell this stock": 15,
            "target": 5,  # Can be legitimate
            "stop loss": 5,  # Can be legitimate
        }

        for indicator, weight in spam_indicators.items():
            if indicator in text:
                score += weight

        # Boost for excessive capitalization or exclamation (approximate)
        if content.title.isupper() and len(content.title) > 10:
            score += 10
        if content.title.count('!') > 2:
            score += 10
        if content.description.count('!!') > 0:
            score += 10

        # Reduce spam risk for educational/disclaimer content
        if "disclaimer" in text or "not advice" in text or "for educational purposes" in text:
            score -= 15
        if "this is not a recommendation" in text:
            score -= 15
        if "consult your financial advisor" in text:
            score -= 15

        return max(min(score, 100.0), 0.0)

    async def _calculate_conversion_potential(self, content: ContentItem) -> float:
        """Calculate conversion potential (likelihood to drive signups)."""
        score = 30.0  # Base score
        text = (content.title + " " + content.description).lower()
        
        # Indicators of high conversion potential
        if "free trial" in text:
            score += 20
        if "demo" in text:
            score += 15
        if "sign up" in text:
            score += 15
        if "register" in text:
            score += 15
        if "get started" in text:
            score += 10
        if "learn more" in text:
            score += 10
        if "visit our website" in text:
            score += 15
        if "check out" in text:
            score += 10
        if "link in bio" in text:
            score += 10
        if "link in description" in text:
            score += 10
        if "website link" in text:
            score += 15
        if "app" in text:
            score += 10
        if "mobile app" in text:
            score += 10
        if "android" in text or "ios" in text:
            score += 5

        # Educational content that leads to tool adoption
        if "tutorial" in text and ("how to use" in text or "walkthrough" in text):
            score += 15
        if "case study" in text:
            score += 10
        if "before and after" in text:
            score += 10
        if "results" in text:
            score += 10

        return max(min(score, 100.0), 0.0)

    async def _calculate_creator_quality_score(self, content: ContentItem) -> float:
        """Calculate creator quality score."""
        score = 50.0  # Base score
        text = (content.title + " " + content.description).lower()
        
        # Creator characteristics
        if "verified" in content.creator_name.lower():
            score += 15
        if "official" in content.creator_name.lower():
            score += 10
        if "analyst" in content.creator_name.lower():
            score += 10
        if "researcher" in content.creator_name.lower():
            score += 10
        if "professor" in content.creator_name.lower():
            score += 15
        if "cfa" in content.creator_name.lower():
            score += 15
        if "ca" in content.creator_name.lower():
            score += 10
        if "mba" in content.creator_name.lower():
            score += 10
        if "ex-" in content.creator_name.lower() and ("bank" in content.creator_name.lower() or "fund" in content.creator_name.lower()):
            score += 15

        # Engagement metrics
        view_count = content.engagement_metrics.get("view_count", 0)
        if isinstance(view_count, (int, float)) and view_count > 0:
            if view_count >= 1000000:
                score += 15
            elif view_count >= 100000:
                score += 10
            elif view_count >= 10000:
                score += 5

        like_count = content.engagement_metrics.get("like_count", 0)
        if isinstance(like_count, (int, float)) and like_count > 0:
            if like_count >= 50000:
                score += 10
            elif like_count >= 10000:
                score += 5

        # Penalty for low engagement or suspicious patterns
        if view_count == 0 and like_count == 0:
            score -= 10
        if view_count > 0 and like_count == 0:
            score -= 5  # Odd ratio

        # Boost for consistent branding
        if "stockscribe" in content.creator_name.lower():
            score += 25  # Self-promotion, but indicates alignment
        if "youtube.com/c/" in content.creator_url or "youtube.com/@" in content.creator_url:
            score += 5

        return max(min(score, 100.0), 0.0)

    async def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """Calculate overall score based on weighted average."""
        weights = {
            "relevance": 0.20,
            "stockscribe_fit": 0.15,
            "audience_fit": 0.15,
            "comment_value": 0.15,
            "conversion_potential": 0.10,
            "creator_quality": 0.10,
            "spam_risk": -0.05,  # Inverted because lower is better
        }

        total = 0.0
        for score_type, weight in weights.items():
            # Keys in the scores dict are without _score suffix (e.g. "relevance")
            raw_score = scores.get(score_type, 0.0)
            if score_type == "spam_risk":
                # For spam risk, lower is better, so we invert
                total += (100.0 - raw_score) * weight
            else:
                total += raw_score * weight

        return max(min(total, 100.0), 0.0)

    def _make_content_decision(self, scores: Dict[str, float]) -> str:
        """Make a decision about whether to comment on content."""
        overall_score = scores.get("overall_score", 0.0)
        spam_risk = scores.get("spam_risk_score", 0.0)
        comment_value = scores.get("comment_value_score", 0.0)
        relevance = scores.get("relevance_score", 0.0)
        audience_fit = scores.get("audience_fit_score", 0.0)

        # Hard rejects
        if overall_score < 50:
            return "reject"
        if spam_risk > 40:
            return "reject"
        if comment_value < 30:
            return "reject"
        if relevance < 40:
            return "reject"
        if audience_fit < 30:
            return "reject"

        # Soft rejects (consider)
        if overall_score < 60:
            return "consider"
        if spam_risk > 30:
            return "consider"
        if comment_value < 50:
            return "consider"
        if relevance < 50:
            return "consider"
        if audience_fit < 40:
            return "consider"

        # Strong accept
        if overall_score >= 80 and comment_value >= 70 and spam_risk < 20:
            return "accept"
        if overall_score >= 70 and relevance >= 70 and audience_fit >= 60:
            return "accept"

        return "consider"

    async def _generate_contextual_comment(self, content: ContentItem, scores: Dict[str, float], campaign_instructions: Dict[str, Any]) -> str:
        """Generate a contextual comment based on content analysis."""
        # Select template based on content characteristics and scores
        text = (content.title + " " + content.description).lower()
        
        # Template selection logic
        if "fundamental analysis" in text or "valuation" in text or "financial statement" in text:
            template = "The fundamental analysis you presented is thorough. Looking at metrics like {metric} gives a clearer picture of intrinsic value. Tools like StockScribe help aggregate these metrics efficiently for comparison."
        elif "technical analysis" in text or "chart pattern" in text or "indicator" in text:
            template = "The technical setup you described is interesting. The {indicator} alignment with {level} suggests {outcome}. Having a way to backtest such setups quickly, as StockScribe allows, would strengthen the analysis."
        elif "portfolio" in text or "allocation" in text or "diversification" in text:
            template = "Portfolio construction is as important as stock selection. The {approach} you mentioned for {aspect} aligns with modern portfolio theory. Being able to stress-test such allocations under different scenarios is where tools like StockScribe add value."
        elif "dividend" in text or "yield" in text or "income" in text:
            template = "Dividend sustainability matters as much as yield. The {metric} you highlighted is a good starting point. Comparing it across peers and checking payout trends over time is easier with a dedicated research platform."
        elif "ipo" in text or "listing" in text or "subscription" in text:
            template = "IPO analysis requires looking beyond the headline numbers. The {aspect} you mentioned is a key consideration. Having access to grey market data and peer comparisons, as some research tools provide, can add context."
        elif "mutual fund" in text or "etf" in text:
            template = "Fund selection involves more than just past returns. The {factor} you pointed out is important for {aspect}. Being able to look under the hood at holdings and overlap, which platforms like StockScribe facilitate, leads to better decisions."
        elif "macro" in text or "economy" in text or "policy" in text:
            template = "The macroeconomic backdrop you described sets the stage. The {indicator} trend you highlighted has historically correlated with {outcome}. Being able to overlay such indicators on stock screens adds another dimension."
        else:
            # Generic template
            template = "The {aspect} you discussed is a key consideration for {context}. Having a systematic way to evaluate {factor} across multiple options, as tools like StockScribe provide, helps in making informed decisions."

        # Fill in placeholders based on content
        filled = template
        
        # Simple placeholder replacement based on content analysis
        if "{metric}" in filled:
            filled = filled.replace("{metric}", "ROE and ROCE")
        if "{indicator}" in filled:
            filled = filled.replace("{indicator}", "RSI")
        if "{level}" in filled:
            filled = filled.replace("{level}", "support/resistance")
        if "{outcome}" in filled:
            filled = filled.replace("{outcome}", "potential breakout")
        if "{approach}" in filled:
            filled = filled.replace("{approach}", "sector-based allocation")
        if "{aspect}" in filled:
            # Use a relevant aspect from the content
            if "risk" in text:
                filled = filled.replace("{aspect}", "risk management")
            elif "return" in text:
                filled = filled.replace("{aspect}", "return potential")
            elif "growth" in text:
                filled = filled.replace("{aspect}", "growth prospects")
            else:
                filled = filled.replace("{aspect}", "investment thesis")
        if "{factor}" in filled:
            filled = filled.replace("{factor}", "valuation metrics")
        if "{context}" in filled:
            filled = filled.replace("{context}", "today's market")
        
        # Add a soft CTA if appropriate and not already promotional
        if scores["comment_value_score"] < 70 and "StockScribe" not in filled:
            # Only add CTA if comment is not already too promotional
            filled += " StockScribe offers tools to streamline this kind of analysis."
        elif "StockScribe" in filled and scores["comment_value_score"] > 80:
            # If already mentioning StockScribe and high comment value, keep it
            pass

        return filled.strip()

    async def _get_campaign_instructions(self) -> Dict[str, Any]:
        """Get campaign instructions from configuration or database."""
        # Return default campaign instructions
        return {
            "name": "StockScribe Investor Acquisition",
            "website": "https://stockscribe.in",
            "target": "Retail investors and traders in India",
            "geography": "India",
            "topics": ["Investing", "Trading", "Indian stocks", "NIFTY", "NSE", "BSE", "Fundamental Analysis", "Technical Analysis"],
            "cta_style": "Soft CTA",
            "comment_style": "Helpful, concise, contextual",
            "primary_goal": "Qualified website visitors and registrations",
        }

    async def _store_content_analysis(self, content: ContentItem, analysis: Dict[str, Any]):
        """Store content analysis in database for tracking."""
        try:
            # We could store this in a separate table for analytics
            # For now, we'll just log it
            self.logger.debug("CONTENT_ANALYSIS_STORED", 
                             content_id=content.content_id,
                             scores=analysis)
        except Exception as e:
            self.logger.error("STORE_ANALYSIS_ERROR", error=str(e))

    async def _store_comment(self, comment: Comment) -> int:
        """Store comment in database and return comment ID."""
        try:
            comment_data = {
                "content_item_id": comment.content_item_id,
                "comment_text": comment.text,
                "strategy_id": 1,  # Default strategy ID (contextual)
                "created_at": comment.created_at,
                "published": 1 if comment.published else 0,
                "quality_score": comment.quality_score,
                "spam_risk": comment.spam_risk,
                "conversion_rate": 0.0,  # Will be updated later
                "clicks": 0,
                "signups": 0,
                "created_by": 1,  # Default user ID (agent)
                "platform": comment.platform,
                "creator_id": comment.creator_id,
                "tracking_url": comment.tracking_url,
                "status": comment.status,
            }
            
            comment_id = self.db.insert("comments", comment_data)
            return comment_id
        except Exception as e:
            self.logger.error("STORE_COMMENT_ERROR", error=str(e))
            raise

    async def _update_comment_published(self, content_item_id: str, published: bool, comment_platform_id: Optional[str] = None):
        """Update comment published status in database."""
        try:
            update_data = {
                "published": 1 if published else 0,
                "published_at": datetime.utcnow().isoformat() if published else None,
            }
            # In a full implementation, we might also store the platform comment ID
            self.db.update("comments", {"content_item_id": content_item_id}, update_data)
        except Exception as e:
            self.logger.error("UPDATE_COMMENT_ERROR", error=str(e))

    async def _get_content_analysis(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Get content analysis from database or cache."""
        # For now, we'll need to re-fetch or cache; stub implementation
        # In a full implementation, we'd join content_items with analysis logs
        try:
            # Get the content item from database (no broken JOIN to content_analysis)
            rows = self.db.select(
                "SELECT * FROM content_items WHERE id = ?", (content_id,)
            )
            
            if rows:
                row = self.db.row_to_dict(rows[0])
                # Extract analysis fields if they exist
                analysis = {
                    "content": ContentItem(
                        platform=row["platform_name"],
                        url=row["url"],
                        title=row["title"],
                        description=row["description"],
                        transcript=row["transcript"],
                        published_date=row["published_date"],
                        creator_id=str(row["creator_id"]),
                        creator_name="",  # Would need to join with accounts
                        creator_url="",
                        engagement_metrics={},
                        existing_comments=[],
                        keywords=row["keywords"] if row["keywords"] else "",
                        search_query="",  # Would need to join with search_queries
                        discovered_at=row["discovered_at"],
                        content_id=str(row["id"]),
                        platform_content_id=row["platform_content_id"] if row["platform_content_id"] else "",
                    ),
                    "scores": {
                        "relevance_score": float(row["relevance_score"]) if row["relevance_score"] is not None else 0.0,
                        "stockscribe_fit_score": float(row["stockscribe_fit_score"]) if row["stockscribe_fit_score"] is not None else 0.0,
                        "audience_fit_score": float(row["audience_fit_score"]) if row["audience_fit_score"] is not None else 0.0,
                        "comment_value_score": float(row["comment_value_score"]) if row["comment_value_score"] is not None else 0.0,
                        "spam_risk_score": float(row["spam_risk_score"]) if row["spam_risk_score"] is not None else 0.0,
                        "conversion_potential_score": float(row["conversion_potential_score"]) if row["conversion_potential_score"] is not None else 0.0,
                        "creator_quality_score": float(row["creator_quality_score"]) if row["creator_quality_score"] is not None else 0.0,
                        "overall_score": float(row["overall_score"]) if row["overall_score"] is not None else 0.0,
                    },
                    "decision": row["status"] if row["status"] else "unknown"
                }
                return analysis
            return None
        except Exception as e:
            self.logger.error("GET_CONTENT_ANALYSIS_ERROR", error=str(e))
            return None

    async def _get_qualified_comments(self) -> List[Comment]:
        """Get qualified comments from queue for publishing."""
        # For now, we'll return an empty list; in a full implementation,
        # we'd query the database for comments with status 'approved' or 'generated'
        # that haven't been published yet.
        return []

    def status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "running": self.running,
            "initialized": self.initialized,
            "platforms": {name: adapter.is_healthy() for name, adapter in self.platforms.items()},
            "config": self.config.all(),
            "db_path": str(self.db.db_path),
        }

    async def stop(self):
        """Stop the agent."""
        self.running = False
        self.logger.info("AGENT_STOPPING")
        await asyncio.sleep(0.1)  # Allow loop to exit
        self.db.close()
        self.logger.info("AGENT_STOPPED")


async def run_agent(agent: HermesSocialAgent) -> None:
    """Run the agent until its stop flag is set."""
    try:
        await agent.start()
    finally:
        await agent.stop()


def main() -> None:
    """Run the continuous agent loop with graceful shutdown handling."""
    agent = HermesSocialAgent()

    def signal_handler(sig, frame):
        print("\nShutting down gracefully...")
        agent.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(run_agent(agent))
    except KeyboardInterrupt:
        print("\nShutting down...")


# For direct execution
if __name__ == "__main__":
    import signal

    main()
