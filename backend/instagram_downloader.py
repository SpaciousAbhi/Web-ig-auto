"""
Instagram Content Downloader
Downloads and processes media files from Instagram
"""
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict
import hashlib
from PIL import Image, ImageEnhance
import logging
from urllib.parse import urlparse
import shutil
from instagram_monitor import ContentItem

class ContentDownloader:
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 3):
        self.download_dir = Path(download_dir)
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger("content_downloader")
        self.session: Optional[aiohttp.ClientSession] = None
        self.download_stats = {"success": 0, "failed": 0, "skipped": 0}
        
        # Create directory structure
        for subdir in ["images", "videos", "stories", "reels", "thumbnails"]:
            (self.download_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def download_content_batch(self, content_items: List[ContentItem]) -> Dict[str, str]:
        """Download a batch of content items"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        download_results = {}
        
        tasks = []
        for item in content_items:
            task = self._download_single_item(semaphore, item)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for item, result in zip(content_items, results):
            if isinstance(result, Exception):
                self.logger.error(f"Download failed for {item.media_id}: {str(result)}")
                download_results[item.media_id] = None
                self.download_stats["failed"] += 1
            else:
                download_results[item.media_id] = result
                if result:
                    self.download_stats["success"] += 1
                else:
                    self.download_stats["skipped"] += 1
        
        return download_results
    
    async def _download_single_item(self, semaphore: asyncio.Semaphore, item: ContentItem) -> Optional[str]:
        """Download a single content item"""
        async with semaphore:
            try:
                # Determine target directory based on content type
                target_dir = self.download_dir / self._get_content_directory(item.media_type)
                
                # Generate filename
                filename = self._generate_filename(item)
                target_path = target_dir / filename
                
                # Skip if already downloaded
                if target_path.exists():
                    self.logger.info(f"Skipping {item.media_id} - already downloaded")
                    item.download_path = str(target_path)
                    item.is_downloaded = True
                    return str(target_path)
                
                # Download the media file
                file_path = await self._download_media_file(item.media_url, target_path)
                
                # Download thumbnail if available and different from main media
                if item.thumbnail_url and item.thumbnail_url != item.media_url:
                    thumbnail_dir = self.download_dir / "thumbnails"
                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_path = thumbnail_dir / thumbnail_filename
                    await self._download_media_file(item.thumbnail_url, thumbnail_path)
                
                # Process the downloaded file based on type
                processed_path = await self._process_downloaded_media(file_path, item)
                
                # Update content item
                item.download_path = processed_path
                item.is_downloaded = True
                
                self.logger.info(f"Successfully downloaded {item.media_id} to {processed_path}")
                return processed_path
                
            except Exception as e:
                self.logger.error(f"Error downloading {item.media_id}: {str(e)}")
                return None
    
    async def _download_media_file(self, url: str, target_path: Path) -> str:
        """Download media file from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    # Create directory if it doesn't exist
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write file content
                    async with aiofiles.open(target_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    return str(target_path)
                else:
                    raise Exception(f"HTTP {response.status} when downloading {url}")
                    
        except Exception as e:
            self.logger.error(f"Failed to download {url}: {str(e)}")
            raise
    
    async def _process_downloaded_media(self, file_path: str, item: ContentItem) -> str:
        """Process downloaded media based on type and requirements"""
        path = Path(file_path)
        
        if item.media_type in ["photo", "image"]:
            return await self._process_image(path, item)
        elif item.media_type in ["video", "reel"]:
            # For now, just return the path - video processing would require FFmpeg
            return str(path)
        elif item.media_type == "story":
            # Stories can be either images or videos
            if self._is_video_file(path):
                return str(path)
            else:
                return await self._process_image(path, item)
        
        return str(path)
    
    async def _process_image(self, image_path: Path, item: ContentItem) -> str:
        """Process downloaded image with optimization and formatting"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Optimize image quality and size
                img = self._optimize_image(img)
                
                # Save processed image
                processed_path = image_path.with_suffix('.jpg')
                img.save(processed_path, 'JPEG', quality=90, optimize=True)
                
                # Remove original if different format
                if processed_path != image_path:
                    image_path.unlink()
                
                return str(processed_path)
                
        except Exception as e:
            self.logger.error(f"Error processing image {image_path}: {str(e)}")
            return str(image_path)
    
    def _optimize_image(self, img: Image.Image) -> Image.Image:
        """Optimize image for Instagram posting"""
        # Resize if too large (Instagram max: 1080x1080 for square posts)
        max_size = 1080
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Enhance image quality slightly
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.05)
        
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.02)
        
        return img
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video"""
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        return file_path.suffix.lower() in video_extensions
    
    def _get_content_directory(self, media_type: str) -> str:
        """Get appropriate directory for content type"""
        type_mapping = {
            "photo": "images",
            "image": "images",
            "video": "videos",
            "reel": "reels",
            "story": "stories"
        }
        return type_mapping.get(media_type, "images")
    
    def _generate_filename(self, item: ContentItem) -> str:
        """Generate unique filename for content item"""
        # Create hash from media ID and URL for uniqueness
        content_hash = hashlib.md5(f"{item.media_id}_{item.media_url}".encode()).hexdigest()[:8]
        
        # Determine file extension from URL
        parsed_url = urlparse(item.media_url)
        path = parsed_url.path
        extension = Path(path).suffix if Path(path).suffix else '.jpg'
        
        # Clean extension
        if not extension or extension == '.':
            extension = '.jpg'
        
        # Generate filename
        timestamp = item.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{item.account_username}_{timestamp}_{content_hash}{extension}"
        
        return filename
    
    def get_download_stats(self) -> Dict[str, int]:
        """Get download statistics"""
        return self.download_stats.copy()