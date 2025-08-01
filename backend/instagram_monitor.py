"""
Instagram Content Monitoring System
Monitors source accounts for new posts, stories, and reels
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from instagrapi import Client
from instagrapi.types import Media, Story

@dataclass
class ContentItem:
    media_id: str
    account_username: str
    media_type: str  # photo, video, reel, story
    caption: str
    media_url: str
    thumbnail_url: Optional[str]
    timestamp: datetime
    view_count: Optional[int]
    like_count: Optional[int]
    comment_count: Optional[int]
    is_downloaded: bool = False
    download_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ContentItem':
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

class ContentMonitor:
    def __init__(self, storage_dir: str = "monitoring_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("content_monitor")
        self.monitoring_state = {}
        self._load_monitoring_state()
        
    def add_source_account(self, username: str, content_types: List[str] = None) -> bool:
        """Add a source account for monitoring"""
        if content_types is None:
            content_types = ["posts", "stories", "reels"]
            
        self.monitoring_state[username] = {
            "content_types": content_types,
            "last_check": None,
            "last_media_id": None,
            "total_monitored": 0,
            "errors": 0,
            "active": True
        }
        self._save_monitoring_state()
        self.logger.info(f"Added source account {username} for monitoring: {content_types}")
        return True
    
    async def monitor_account(self, username: str, client: Client) -> List[ContentItem]:
        """Monitor a single account for new content"""
        try:
            account_state = self.monitoring_state.get(username, {})
            if not account_state.get("active", True):
                return []
            
            new_content = []
            content_types = account_state.get("content_types", ["posts"])
            
            self.logger.info(f"Starting monitoring for {username} - types: {content_types}")
            
            # Monitor regular posts
            if "posts" in content_types:
                posts = await self._get_recent_posts(client, username, account_state)
                new_content.extend(posts)
            
            # Monitor stories
            if "stories" in content_types:
                stories = await self._get_recent_stories(client, username)
                new_content.extend(stories)
            
            # Monitor reels
            if "reels" in content_types:
                reels = await self._get_recent_reels(client, username, account_state)
                new_content.extend(reels)
            
            # Update monitoring state
            if new_content:
                self.monitoring_state[username]["last_check"] = datetime.now()
                self.monitoring_state[username]["total_monitored"] += len(new_content)
                self._save_monitoring_state()
                
                self.logger.info(f"Found {len(new_content)} new items from {username}")
            else:
                self.logger.info(f"No new content found for {username}")
            
            return new_content
            
        except Exception as e:
            self.logger.error(f"Error monitoring account {username}: {str(e)}")
            if username in self.monitoring_state:
                self.monitoring_state[username]["errors"] = self.monitoring_state[username].get("errors", 0) + 1
                self._save_monitoring_state()
            return []
    
    async def _get_recent_posts(self, client: Client, username: str, account_state: Dict) -> List[ContentItem]:
        """Retrieve recent posts from an account"""
        try:
            user_id = client.user_id_from_username(username)
            medias = client.user_medias(user_id, amount=5)  # Get last 5 posts
            
            last_media_id = account_state.get("last_media_id")
            new_posts = []
            
            for media in medias:
                # Stop if we've reached previously processed content
                if last_media_id and str(media.pk) == last_media_id:
                    break
                
                content_item = self._create_content_item_from_media(media, username)
                new_posts.append(content_item)
            
            # Update last processed media ID to the most recent
            if new_posts and username in self.monitoring_state:
                self.monitoring_state[username]["last_media_id"] = new_posts[0].media_id
            
            if new_posts:
                self.logger.info(f"Found {len(new_posts)} new posts from {username}")
            
            return new_posts
            
        except Exception as e:
            self.logger.error(f"Error getting posts from {username}: {str(e)}")
            return []
    
    async def _get_recent_stories(self, client: Client, username: str) -> List[ContentItem]:
        """Retrieve recent stories from an account"""
        try:
            user_id = client.user_id_from_username(username)
            stories = client.user_stories(user_id)
            
            story_items = []
            for story in stories:
                content_item = self._create_content_item_from_story(story, username)
                story_items.append(content_item)
            
            if story_items:
                self.logger.info(f"Found {len(story_items)} stories from {username}")
            
            return story_items
            
        except Exception as e:
            self.logger.error(f"Error getting stories from {username}: {str(e)}")
            return []
    
    async def _get_recent_reels(self, client: Client, username: str, account_state: Dict) -> List[ContentItem]:
        """Retrieve recent reels from an account"""
        try:
            user_id = client.user_id_from_username(username)
            # Get recent media and filter for reels
            medias = client.user_medias(user_id, amount=10)
            
            reels = []
            for media in medias:
                if media.media_type == 2 and hasattr(media, 'video_url'):  # Video type
                    # Additional checks to identify reels vs regular videos
                    if self._is_reel(media):
                        content_item = self._create_content_item_from_media(media, username, "reel")
                        reels.append(content_item)
            
            if reels:
                self.logger.info(f"Found {len(reels)} reels from {username}")
            
            return reels
            
        except Exception as e:
            self.logger.error(f"Error getting reels from {username}: {str(e)}")
            return []
    
    def _create_content_item_from_media(self, media: Media, username: str, content_type: str = None) -> ContentItem:
        """Create ContentItem from Instagram media object"""
        if content_type is None:
            content_type = "photo" if media.media_type == 1 else "video"
        
        # Get the best available media URL
        media_url = None
        if hasattr(media, 'video_url') and media.video_url:
            media_url = media.video_url
        elif hasattr(media, 'image_versions2') and media.image_versions2:
            # Get highest quality image
            candidates = media.image_versions2.get('candidates', [])
            if candidates:
                media_url = candidates[0]['url']
        
        # Fallback to thumbnail
        if not media_url:
            media_url = media.thumbnail_url
        
        return ContentItem(
            media_id=str(media.pk),
            account_username=username,
            media_type=content_type,
            caption=media.caption_text if media.caption_text else "",
            media_url=media_url,
            thumbnail_url=media.thumbnail_url,
            timestamp=media.taken_at,
            view_count=getattr(media, 'view_count', None),
            like_count=media.like_count,
            comment_count=media.comment_count
        )
    
    def _create_content_item_from_story(self, story: Story, username: str) -> ContentItem:
        """Create ContentItem from Instagram story object"""
        media_url = None
        if hasattr(story, 'video_url') and story.video_url:
            media_url = story.video_url
        elif hasattr(story, 'image_versions2') and story.image_versions2:
            candidates = story.image_versions2.get('candidates', [])
            if candidates:
                media_url = candidates[0]['url']
        
        if not media_url:
            media_url = story.thumbnail_url
        
        return ContentItem(
            media_id=str(story.pk),
            account_username=username,
            media_type="story",
            caption="",  # Stories typically don't have captions
            media_url=media_url,
            thumbnail_url=story.thumbnail_url,
            timestamp=story.taken_at,
            view_count=getattr(story, 'view_count', None),
            like_count=0,  # Stories don't have likes
            comment_count=0
        )
    
    def _is_reel(self, media: Media) -> bool:
        """Determine if media is a reel based on various indicators"""
        # Check for reel-specific attributes or patterns
        if hasattr(media, 'clips_metadata') and media.clips_metadata:
            return True
        
        # Check for product type
        if hasattr(media, 'product_type') and media.product_type == 'clips':
            return True
            
        # Additional heuristics can be added here
        return False
    
    def _load_monitoring_state(self):
        """Load monitoring state from disk"""
        state_file = self.storage_dir / "monitoring_state.json"
        try:
            if state_file.exists():
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    # Convert timestamp strings back to datetime objects
                    for username, state in data.items():
                        if state.get("last_check"):
                            state["last_check"] = datetime.fromisoformat(state["last_check"])
                    self.monitoring_state = data
                    self.logger.info("Loaded monitoring state from disk")
        except Exception as e:
            self.logger.error(f"Error loading monitoring state: {str(e)}")
    
    def _save_monitoring_state(self):
        """Save monitoring state to disk"""
        state_file = self.storage_dir / "monitoring_state.json"
        try:
            # Convert datetime objects to strings for JSON serialization
            serializable_state = {}
            for username, state in self.monitoring_state.items():
                serializable_state[username] = state.copy()
                if state.get("last_check"):
                    serializable_state[username]["last_check"] = state["last_check"].isoformat()
            
            with open(state_file, 'w') as f:
                json.dump(serializable_state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving monitoring state: {str(e)}")
    
    def get_monitoring_stats(self) -> Dict:
        """Get monitoring statistics"""
        stats = {
            "total_accounts": len(self.monitoring_state),
            "active_accounts": sum(1 for state in self.monitoring_state.values() if state.get("active", True)),
            "total_monitored": sum(state.get("total_monitored", 0) for state in self.monitoring_state.values()),
            "accounts": self.monitoring_state.copy()
        }
        
        # Convert datetime objects for JSON serialization
        for username, account_data in stats["accounts"].items():
            if account_data.get("last_check"):
                account_data["last_check"] = account_data["last_check"].isoformat()
        
        return stats