"""
Instagram Content Uploader
Uploads content to destination Instagram accounts
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import logging
from dataclasses import dataclass
from instagrapi import Client
from instagram_monitor import ContentItem

@dataclass
class UploadConfig:
    add_credit: bool = True
    credit_format: str = "📸 @{username}"
    use_hashtags: bool = True
    max_hashtags: int = 25
    add_call_to_action: bool = False
    cta_text: str = "Follow for more! 🔥"
    
class ContentUploader:
    def __init__(self, upload_config: UploadConfig = None):
        self.config = upload_config or UploadConfig()
        self.logger = logging.getLogger("content_uploader")
        self.upload_stats = {}
        self.rate_limits = {}
        
        # Instagram rate limits (conservative estimates)
        self.rate_limits_config = {
            "posts_per_hour": 3,
            "stories_per_hour": 8,
        }
    
    async def upload_content_item(self, content_item: ContentItem, destination_account: str, 
                                client: Client) -> bool:
        """Upload a single content item to destination account"""
        try:
            # Check rate limits
            if not self._check_rate_limit(destination_account, content_item.media_type):
                self.logger.warning(f"Rate limit reached for {destination_account}, skipping upload")
                return False
            
            # Check if file exists
            if not content_item.download_path or not Path(content_item.download_path).exists():
                self.logger.error(f"File not found for {content_item.media_id}: {content_item.download_path}")
                return False
            
            # Prepare content for upload
            caption = self._generate_caption(content_item)
            file_path = Path(content_item.download_path)
            
            self.logger.info(f"Uploading {content_item.media_type} from {content_item.account_username} to {destination_account}")
            
            # Upload based on content type
            success = False
            if content_item.media_type in ["photo", "image"]:
                success = await self._upload_photo(client, file_path, caption)
            elif content_item.media_type == "video":
                success = await self._upload_video(client, file_path, caption)
            elif content_item.media_type == "reel":
                success = await self._upload_reel(client, file_path, caption)
            elif content_item.media_type == "story":
                success = await self._upload_story(client, file_path, content_item)
            
            # Update statistics and rate limits
            if success:
                self._update_upload_stats(destination_account, content_item.media_type, True)
                self._update_rate_limit(destination_account, content_item.media_type)
                self.logger.info(f"Successfully uploaded {content_item.media_id} to {destination_account}")
            else:
                self._update_upload_stats(destination_account, content_item.media_type, False)
                self.logger.error(f"Failed to upload {content_item.media_id} to {destination_account}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Upload error for {content_item.media_id}: {str(e)}")
            self._update_upload_stats(destination_account, content_item.media_type, False)
            return False
    
    async def _upload_photo(self, client: Client, file_path: Path, caption: str) -> bool:
        """Upload photo to Instagram"""
        try:
            media = client.photo_upload(file_path, caption)
            await self._add_random_delay("photo_upload")
            return media is not None
        except Exception as e:
            self.logger.error(f"Photo upload failed: {str(e)}")
            return False
    
    async def _upload_video(self, client: Client, file_path: Path, caption: str) -> bool:
        """Upload video to Instagram"""
        try:
            media = client.video_upload(file_path, caption)
            await self._add_random_delay("video_upload")
            return media is not None
        except Exception as e:
            self.logger.error(f"Video upload failed: {str(e)}")
            return False
    
    async def _upload_reel(self, client: Client, file_path: Path, caption: str) -> bool:
        """Upload reel to Instagram"""
        try:
            # Use clip_upload for reels
            media = client.clip_upload(file_path, caption)
            await self._add_random_delay("reel_upload")
            return media is not None
        except Exception as e:
            self.logger.error(f"Reel upload failed: {str(e)}")
            return False
    
    async def _upload_story(self, client: Client, file_path: Path, content_item: ContentItem) -> bool:
        """Upload story to Instagram"""
        try:
            # Determine if it's a photo or video story
            if self._is_video_file(file_path):
                media = client.video_upload_to_story(file_path)
            else:
                media = client.photo_upload_to_story(file_path)
            
            await self._add_random_delay("story_upload")
            return media is not None
        except Exception as e:
            self.logger.error(f"Story upload failed: {str(e)}")
            return False
    
    def _generate_caption(self, content_item: ContentItem) -> str:
        """Generate appropriate caption for content"""
        caption_parts = []
        
        # Original caption (if available and appropriate)
        if content_item.caption and len(content_item.caption.strip()) > 0:
            # Clean and truncate caption if necessary
            original_caption = self._clean_caption(content_item.caption)
            if len(original_caption) <= 1500:  # Leave room for other elements
                caption_parts.append(original_caption)
        
        # Add credit if configured
        if self.config.add_credit:
            credit = self.config.credit_format.format(username=content_item.account_username)
            caption_parts.append(credit)
        
        # Add call to action if configured
        if self.config.add_call_to_action:
            caption_parts.append(self.config.cta_text)
        
        # Add hashtags if configured
        if self.config.use_hashtags:
            hashtags = self._generate_hashtags(content_item)
            if hashtags:
                caption_parts.append(hashtags)
        
        # Combine all parts
        caption = "\n\n".join(caption_parts)
        
        # Ensure caption doesn't exceed Instagram's limit (2200 characters)
        if len(caption) > 2200:
            caption = caption[:2180] + "..."
        
        return caption
    
    def _clean_caption(self, caption: str) -> str:
        """Clean and prepare caption text"""
        # Remove excessive whitespace
        caption = " ".join(caption.split())
        
        # Remove or replace problematic characters
        caption = caption.replace("\u2063", "")  # Remove invisible separator
        
        # Remove existing hashtags to avoid duplication
        lines = caption.split('\n')
        clean_lines = []
        for line in lines:
            if not line.strip().startswith('#'):
                clean_lines.append(line)
        
        return '\n'.join(clean_lines).strip()
    
    def _generate_hashtags(self, content_item: ContentItem) -> str:
        """Generate relevant hashtags for content"""
        hashtags = []
        
        # Content-type specific hashtags
        type_hashtags = {
            "photo": ["#photography", "#photooftheday", "#beautiful", "#amazing"],
            "video": ["#video", "#videos", "#awesome", "#cool"],
            "reel": ["#reels", "#reelsinstagram", "#trending", "#viral"],
            "story": ["#story", "#stories", "#daily", "#update"]
        }
        
        # Add type-specific hashtags
        if content_item.media_type in type_hashtags:
            hashtags.extend(type_hashtags[content_item.media_type])
        
        # Add source-based hashtags (if appropriate)
        source_based = self._get_source_hashtags(content_item.account_username)
        hashtags.extend(source_based)
        
        # Add generic engagement hashtags
        engagement_hashtags = [
            "#love", "#instagood", "#follow", "#like4like",
            "#followme", "#explore", "#discover", "#amazing"
        ]
        hashtags.extend(random.sample(engagement_hashtags, min(4, len(engagement_hashtags))))
        
        # Limit total hashtags
        hashtags = hashtags[:self.config.max_hashtags]
        
        return " ".join(hashtags) if hashtags else ""
    
    def _get_source_hashtags(self, source_username: str) -> List[str]:
        """Get hashtags based on source account"""
        source_mapping = {
            "natgeo": ["#nature", "#wildlife", "#earth", "#planet"],
            "bbcearth": ["#earth", "#planet", "#documentary", "#nature"],
            "travel": ["#travel", "#wanderlust", "#adventure", "#explore"],
            "food": ["#food", "#foodie", "#delicious", "#cooking"],
            "nationalgeographic": ["#nature", "#wildlife", "#photography", "#earth"]
        }
        
        for key, tags in source_mapping.items():
            if key.lower() in source_username.lower():
                return tags
        
        return []
    
    def _check_rate_limit(self, account: str, content_type: str) -> bool:
        """Check if account has hit rate limits"""
        current_time = datetime.now()
        account_limits = self.rate_limits.get(account, {})
        
        # Check hourly limits based on content type
        if content_type in ["photo", "video", "reel"]:
            limit_key = "posts"
            max_per_hour = self.rate_limits_config["posts_per_hour"]
        elif content_type == "story":
            limit_key = "stories"
            max_per_hour = self.rate_limits_config["stories_per_hour"]
        else:
            return True  # Unknown type, allow
        
        # Get recent actions for this account and type
        recent_actions = account_limits.get(limit_key, [])
        
        # Remove actions older than 1 hour
        hour_ago = current_time - timedelta(hours=1)
        recent_actions = [action_time for action_time in recent_actions if action_time > hour_ago]
        
        # Check if under limit
        return len(recent_actions) < max_per_hour
    
    def _update_rate_limit(self, account: str, content_type: str):
        """Update rate limit tracking"""
        current_time = datetime.now()
        
        if account not in self.rate_limits:
            self.rate_limits[account] = {}
        
        # Determine limit key
        if content_type in ["photo", "video", "reel"]:
            limit_key = "posts"
        elif content_type == "story":
            limit_key = "stories"
        else:
            return
        
        # Add current time to tracking
        if limit_key not in self.rate_limits[account]:
            self.rate_limits[account][limit_key] = []
        
        self.rate_limits[account][limit_key].append(current_time)
        
        # Keep only recent actions (last 2 hours for safety)
        two_hours_ago = current_time - timedelta(hours=2)
        self.rate_limits[account][limit_key] = [
            action_time for action_time in self.rate_limits[account][limit_key]
            if action_time > two_hours_ago
        ]
    
    async def _add_random_delay(self, action_type: str):
        """Add human-like delays between actions"""
        delay_ranges = {
            "photo_upload": (60, 180),
            "video_upload": (90, 240),
            "reel_upload": (75, 200),
            "story_upload": (30, 90)
        }
        
        min_delay, max_delay = delay_ranges.get(action_type, (60, 120))
        delay = random.uniform(min_delay, max_delay)
        
        self.logger.debug(f"Adding {delay:.1f}s delay after {action_type}")
        await asyncio.sleep(delay)
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video"""
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        return file_path.suffix.lower() in video_extensions
    
    def _update_upload_stats(self, account: str, content_type: str, success: bool):
        """Update upload statistics"""
        if account not in self.upload_stats:
            self.upload_stats[account] = {
                "total_uploads": 0,
                "successful_uploads": 0,
                "failed_uploads": 0,
                "by_type": {}
            }
        
        stats = self.upload_stats[account]
        stats["total_uploads"] += 1
        
        if success:
            stats["successful_uploads"] += 1
        else:
            stats["failed_uploads"] += 1
        
        # Track by content type
        if content_type not in stats["by_type"]:
            stats["by_type"][content_type] = {"success": 0, "failed": 0}
        
        if success:
            stats["by_type"][content_type]["success"] += 1
        else:
            stats["by_type"][content_type]["failed"] += 1
    
    def get_upload_stats(self, account: str = None) -> Dict:
        """Get upload statistics"""
        if account:
            return self.upload_stats.get(account, {})
        return self.upload_stats.copy()