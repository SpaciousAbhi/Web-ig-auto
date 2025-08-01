"""
Instagram Automation Engine
Main orchestrator for Instagram content monitoring and posting
"""
import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime

from instagram_auth import InstagramAuthenticator
from instagram_monitor import ContentMonitor
from instagram_downloader import ContentDownloader
from instagram_uploader import ContentUploader, UploadConfig

class InstagramAutomationEngine:
    def __init__(self, data_dir: str = "instagram_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger("instagram_engine")
        
        # Initialize components
        self.monitor = ContentMonitor(str(self.data_dir / "monitoring"))
        self.uploader = ContentUploader()
        
        # Store authenticated clients
        self.authenticated_clients: Dict[str, InstagramAuthenticator] = {}
        
        # Task tracking
        self.active_tasks: Dict[str, Dict] = {}
        self._load_tasks()
    
    def add_instagram_account(self, username: str, password: str) -> bool:
        """Add and authenticate an Instagram account"""
        try:
            authenticator = InstagramAuthenticator(
                username, 
                password, 
                str(self.data_dir / "sessions")
            )
            
            if authenticator.authenticate():
                self.authenticated_clients[username] = authenticator
                self.logger.info(f"Successfully added Instagram account: {username}")
                return True
            else:
                self.logger.error(f"Failed to authenticate Instagram account: {username}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding Instagram account {username}: {str(e)}")
            return False
    
    def create_monitoring_task(self, task_name: str, source_accounts: List[str], 
                             destination_accounts: List[str], content_types: List[str]) -> bool:
        """Create a new content monitoring and posting task"""
        try:
            # Validate destination accounts are authenticated
            for dest_account in destination_accounts:
                if dest_account not in self.authenticated_clients:
                    self.logger.error(f"Destination account {dest_account} not authenticated")
                    return False
            
            # Add source accounts to monitor
            for source_account in source_accounts:
                self.monitor.add_source_account(source_account, content_types)
            
            # Create task
            task_id = f"task_{len(self.active_tasks) + 1}_{int(datetime.now().timestamp())}"
            task = {
                "id": task_id,
                "name": task_name,
                "source_accounts": source_accounts,
                "destination_accounts": destination_accounts,
                "content_types": content_types,
                "enabled": True,
                "created_at": datetime.now(),
                "last_run": None,
                "last_processed_count": 0,
                "total_processed": 0,
                "errors": 0
            }
            
            self.active_tasks[task_id] = task
            self._save_tasks()
            
            self.logger.info(f"Created task {task_name} monitoring {len(source_accounts)} accounts")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating task {task_name}: {str(e)}")
            return False
    
    async def run_task(self, task_id: str) -> Dict:
        """Run a specific task"""
        if task_id not in self.active_tasks:
            return {"success": False, "error": "Task not found"}
        
        task = self.active_tasks[task_id]
        if not task.get("enabled", True):
            return {"success": False, "error": "Task is disabled"}
        
        self.logger.info(f"Running task: {task['name']}")
        
        try:
            # Get a client for monitoring (use first destination account)
            dest_account = task["destination_accounts"][0]
            monitor_client = self.authenticated_clients[dest_account].get_client()
            
            if not monitor_client:
                return {"success": False, "error": "Failed to authenticate monitoring account"}
            
            # Monitor all source accounts
            all_new_content = []
            for source_account in task["source_accounts"]:
                content = await self.monitor.monitor_account(source_account, monitor_client)
                all_new_content.extend(content)
            
            if not all_new_content:
                self.logger.info(f"No new content found for task {task['name']}")
                task["last_run"] = datetime.now()
                task["last_processed_count"] = 0
                self._save_tasks()
                return {"success": True, "processed_count": 0, "message": "No new content found"}
            
            self.logger.info(f"Found {len(all_new_content)} new items for task {task['name']}")
            
            # Download content
            async with ContentDownloader(str(self.data_dir / "downloads")) as downloader:
                download_results = await downloader.download_content_batch(all_new_content)
            
            # Filter successfully downloaded content
            downloaded_content = []
            for item in all_new_content:
                if download_results.get(item.media_id) and item.is_downloaded:
                    downloaded_content.append(item)
            
            self.logger.info(f"Successfully downloaded {len(downloaded_content)} items")
            
            # Upload to destination accounts
            upload_results = []
            for dest_account in task["destination_accounts"]:
                client = self.authenticated_clients[dest_account].get_client()
                if not client:
                    self.logger.error(f"Failed to authenticate {dest_account}")
                    continue
                
                for content_item in downloaded_content:
                    success = await self.uploader.upload_content_item(
                        content_item, dest_account, client
                    )
                    upload_results.append({
                        "content_id": content_item.media_id,
                        "destination": dest_account,
                        "success": success
                    })
                    
                    # Add delay between uploads to different accounts
                    await asyncio.sleep(30)
            
            # Update task statistics
            successful_uploads = sum(1 for result in upload_results if result["success"])
            task["last_run"] = datetime.now()
            task["last_processed_count"] = successful_uploads
            task["total_processed"] += successful_uploads
            self._save_tasks()
            
            self.logger.info(f"Task {task['name']} completed: {successful_uploads} successful uploads")
            
            return {
                "success": True,
                "processed_count": successful_uploads,
                "found_content": len(all_new_content),
                "downloaded": len(downloaded_content),
                "upload_results": upload_results
            }
            
        except Exception as e:
            self.logger.error(f"Error running task {task_id}: {str(e)}")
            task["errors"] = task.get("errors", 0) + 1
            self._save_tasks()
            return {"success": False, "error": str(e)}
    
    async def run_all_enabled_tasks(self) -> Dict:
        """Run all enabled tasks"""
        results = {}
        enabled_tasks = [task_id for task_id, task in self.active_tasks.items() if task.get("enabled", True)]
        
        self.logger.info(f"Running {len(enabled_tasks)} enabled tasks")
        
        for task_id in enabled_tasks:
            try:
                result = await self.run_task(task_id)
                results[task_id] = result
                
                # Add delay between tasks
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error running task {task_id}: {str(e)}")
                results[task_id] = {"success": False, "error": str(e)}
        
        return results
    
    def toggle_task(self, task_id: str, enabled: bool) -> bool:
        """Enable or disable a task"""
        if task_id not in self.active_tasks:
            return False
        
        self.active_tasks[task_id]["enabled"] = enabled
        self._save_tasks()
        
        status = "enabled" if enabled else "disabled"
        self.logger.info(f"Task {task_id} {status}")
        return True
    
    def get_task_status(self, task_id: str = None) -> Dict:
        """Get status of specific task or all tasks"""
        if task_id:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id].copy()
                # Convert datetime objects for JSON serialization
                if task.get("created_at"):
                    task["created_at"] = task["created_at"].isoformat()
                if task.get("last_run"):
                    task["last_run"] = task["last_run"].isoformat()
                return task
            return None
        else:
            # Return all tasks
            all_tasks = {}
            for tid, task in self.active_tasks.items():
                task_copy = task.copy()
                if task_copy.get("created_at"):
                    task_copy["created_at"] = task_copy["created_at"].isoformat()
                if task_copy.get("last_run"):
                    task_copy["last_run"] = task_copy["last_run"].isoformat()
                all_tasks[tid] = task_copy
            return all_tasks
    
    def get_monitoring_stats(self) -> Dict:
        """Get monitoring statistics"""
        return self.monitor.get_monitoring_stats()
    
    def get_upload_stats(self) -> Dict:
        """Get upload statistics"""
        return self.uploader.get_upload_stats()
    
    def _load_tasks(self):
        """Load tasks from disk"""
        tasks_file = self.data_dir / "tasks.json"
        try:
            if tasks_file.exists():
                with open(tasks_file, 'r') as f:
                    data = json.load(f)
                    # Convert timestamp strings back to datetime objects
                    for task_id, task in data.items():
                        if task.get("created_at"):
                            task["created_at"] = datetime.fromisoformat(task["created_at"])
                        if task.get("last_run"):
                            task["last_run"] = datetime.fromisoformat(task["last_run"])
                    self.active_tasks = data
                    self.logger.info(f"Loaded {len(self.active_tasks)} tasks from disk")
        except Exception as e:
            self.logger.error(f"Error loading tasks: {str(e)}")
    
    def _save_tasks(self):
        """Save tasks to disk"""
        tasks_file = self.data_dir / "tasks.json"
        try:
            # Convert datetime objects to strings for JSON serialization
            serializable_tasks = {}
            for task_id, task in self.active_tasks.items():
                serializable_task = task.copy()
                if task.get("created_at"):
                    serializable_task["created_at"] = task["created_at"].isoformat()
                if task.get("last_run"):
                    serializable_task["last_run"] = task["last_run"].isoformat()
                serializable_tasks[task_id] = serializable_task
            
            with open(tasks_file, 'w') as f:
                json.dump(serializable_tasks, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving tasks: {str(e)}")