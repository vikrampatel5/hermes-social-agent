"""YouTube platform adapter for Hermes Social Engagement Agent.

Uses youtube-transcript-api for transcripts and Google YouTube Data API v3
for search and metadata (requires API key for search).
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from platforms.base import PlatformAdapter, ContentItem, Comment

logger = logging.getLogger(__name__)

class YouTubeAdapter(PlatformAdapter):
    """YouTube platform adapter."""

    def name(self) -> str:
        return "youtube"

    def init(self) -> bool:
        """Initialize YouTube API client if API key is available."""
        self.supported_capabilities = {
            'search', 'get_content', 'get_creator',
            'get_comments', 'publish_comment', 'get_metrics',
            'health_check', 'get_comment_status'
        }
        self._initialized = False
        
        # Try to initialize YouTube Data API
        api_key = os.getenv("YOUTUBE_API_KEY")
        if api_key:
            try:
                from googleapiclient.discovery import build
                self.youtube = build('youtube', 'v3', developerKey=api_key)
                self._initialized = True
                logger.info("YouTube Data API initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize YouTube Data API: {e}")
                self.youtube = None
        else:
            logger.warning("YOUTUBE_API_KEY not set; YouTube search disabled")
            self.youtube = None
        
        # youtube-transcript-api does not require initialization
        self.transcript_api_available = True
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            self.YouTubeTranscriptApi = YouTubeTranscriptApi
        except ImportError:
            self.transcript_api_available = False
            logger.warning("youtube-transcript-api not available")
        
        return self.transcript_api_available or self.youtube is not None

    def search(self, query: str, max_results: int = 20) -> List[ContentItem]:
        """Search YouTube for content matching query."""
        if not self.youtube:
            logger.warning("YouTube Data API not available; skipping search")
            return []
        
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=min(max_results, 50),
                type='video',
                order='relevance',
                publishedAfter=(datetime.utcnow() - timedelta(days=30)).isoformat('T') + 'Z'
            ).execute()
            
            results = []
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                # Get detailed video info
                video_response = self.youtube.videos().list(
                    part='snippet,contentDetails,statistics',
                    id=video_id
                ).execute()
                
                if not video_response.get('items'):
                    continue
                
                video = video_response['items'][0]
                video_snippet = video['snippet']
                stats = video.get('statistics', {})
                
                content = ContentItem(
                    platform="youtube",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=video_snippet.get('title', ''),
                    description=video_snippet.get('description', ''),
                    published_date=video_snippet.get('publishedAt', ''),
                    creator_name=video_snippet.get('channelTitle', ''),
                    creator_id=video_snippet.get('channelId', ''),
                    creator_url=f"https://www.youtube.com/channel/{video_snippet.get('channelId', '')}",
                    engagement_metrics={
                        'view_count': int(stats.get('viewCount', 0)),
                        'like_count': int(stats.get('likeCount', 0)),
                        'comment_count': int(stats.get('commentCount', 0)),
                    },
                    content_type="video",
                    search_query=query,
                    discovered_at=datetime.utcnow().isoformat(),
                    platform_content_id=video_id,
                    content_id=f"yt_{video_id}"
                )
                
                # Get transcript if available
                if self.transcript_api_available:
                    content.transcript = self._get_transcript(video_id)
                
                results.append(content)
                
                if len(results) >= max_results:
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    def _get_transcript(self, video_id: str) -> str:
        """Fetch YouTube transcript for a video."""
        if not self.transcript_api_available:
            return ""
        try:
            transcript_list = self.YouTubeTranscriptApi.fetch(video_id, languages=['en'])
            # transcript_list is a list of snippets; join text
            return " ".join([snippet.text for snippet in transcript_list])
        except Exception as e:
            logger.debug(f"Could not get transcript for {video_id}: {e}")
            return ""

    def get_content(self, content_id: str) -> Optional[ContentItem]:
        """Get detailed YouTube video content."""
        if not self.youtube:
            return None
        
        # Extract video ID from content_id (format: yt_{video_id})
        if content_id.startswith('yt_'):
            video_id = content_id[3:]
        else:
            video_id = content_id
        
        try:
            video_response = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            ).execute()
            
            if not video_response.get('items'):
                return None
            
            item = video_response['items'][0]
            snippet = item['snippet']
            stats = item.get('statistics', {})
            
            content = ContentItem(
                platform="youtube",
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=snippet.get('title', ''),
                description=snippet.get('description', ''),
                published_date=snippet.get('publishedAt', ''),
                creator_name=snippet.get('channelTitle', ''),
                creator_id=snippet.get('channelId', ''),
                creator_url=f"https://www.youtube.com/channel/{snippet.get('channelId', '')}",
                engagement_metrics={
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                    'comment_count': int(stats.get('commentCount', 0)),
                },
                content_type="video",
                platform_content_id=video_id,
                content_id=f"yt_{video_id}",
                discovered_at=datetime.utcnow().isoformat()
            )
            
            # Get transcript
            if self.transcript_api_available:
                content.transcript = self._get_transcript(video_id)
            
            # Get existing comments (limited due to API quota)
            content.existing_comments = self.get_comments(video_id)
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to get YouTube content {video_id}: {e}")
            return None

    def get_creator(self, creator_id: str) -> Optional[Dict]:
        """Get YouTube channel information."""
        if not self.youtube:
            return None
        
        try:
            response = self.youtube.channels().list(
                part='snippet,statistics',
                id=creator_id
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            snippet = item['snippet']
            stats = item.get('statistics', {})
            
            return {
                'id': creator_id,
                'name': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'url': f"https://www.youtube.com/channel/{creator_id}",
                'subscribers': int(stats.get('subscriberCount', 0)),
                'view_count': int(stats.get('viewCount', 0)),
                'video_count': int(stats.get('videoCount', 0)),
            }
        except Exception as e:
            logger.error(f"Failed to get YouTube creator {creator_id}: {e}")
            return None

    def get_comments(self, content_id: str) -> List[str]:
        """Get existing YouTube comments on a video."""
        if not self.youtube:
            return []
        
        # Extract video ID
        if content_id.startswith('yt_'):
            video_id = content_id[3:]
        else:
            video_id = content_id
        
        comments = []
        try:
            # Get comment threads (limited to avoid quota issues)
            response = self.youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=20,
                order='relevance'
            ).execute()
            
            for item in response.get('items', []):
                comment_snippet = item['snippet']['topLevelComment']['snippet']
                comment_text = comment_snippet.get('textDisplay', '')
                if comment_text:
                    comments.append(comment_text)
                    
        except Exception as e:
            logger.debug(f"Could not get comments for {video_id}: {e}")
        
        return comments

    def publish_comment(self, comment: Comment, content_item: ContentItem) -> Dict:
        """Publish a comment on YouTube.
        
        Note: YouTube comment posting requires OAuth2 authentication, which is
        complex to implement. For now, we only support dry-run mode.
        In the future, this could be implemented using google-auth and
        youtube.commentThreads().insert() with proper OAuth credentials.
        """
        if self.config.get("DRY_RUN", True):
            return {
                'status': 'dry_run',
                'comment': comment.text,
                'content_url': content_item.url,
                'message': 'Comment saved for review (dry-run mode)'
            }
        else:
            # In production, we would attempt to publish via OAuth2
            # For now, return error indicating OAuth2 required
            return {
                'status': 'error',
                'error': 'YouTube publishing requires OAuth2 authentication (not implemented)',
                'comment_id': None
            }

    def get_comment_status(self, comment_id: str) -> Dict:
        """Check status of a YouTube comment."""
        # YouTube does not provide a simple API to check comment status by ID
        # without knowing the video and having OAuth2 scope.
        return {
            'status': 'unknown',
            'available': False
        }

    def get_metrics(self, content_item_id: str) -> Dict:
        """Get YouTube video metrics."""
        if not self.youtube:
            return {}
        
        # Extract video ID
        if content_item_id.startswith('yt_'):
            video_id = content_item_id[3:]
        else:
            video_id = content_item_id
        
        try:
            response = self.youtube.videos().list(
                part='statistics',
                id=video_id
            ).execute()
            
            if response.get('items'):
                stats = response['items'][0].get('statistics', {})
                return {
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                }
            return {}
        except Exception as e:
            logger.error(f"Failed to get YouTube metrics for {video_id}: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if YouTube API is accessible."""
        if not self.youtube:
            return self.transcript_api_available  # At least transcript API works
        
        try:
            # Simple request to check API availability
            self.youtube.search().list(
                q='test',
                part='id',
                maxResults=1
            ).execute()
            return True
        except Exception:
            return False