from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import asyncio

# Import Instagram automation components
from instagram_engine import InstagramAutomationEngine


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize Instagram automation engine
instagram_engine = InstagramAutomationEngine()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Instagram Account Models
class InstagramAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)

class InstagramAccountCreate(BaseModel):
    username: str
    password: str

class InstagramAccountRemove(BaseModel):
    username: str

# Task Models with Real Instagram Integration
class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    sourceUsername: List[str]
    destinationAccounts: List[str]
    contentTypes: Dict[str, bool]
    enabled: bool = True
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    lastRun: Optional[datetime] = None
    lastProcessedCount: Optional[int] = None

class TaskCreate(BaseModel):
    name: str
    sourceUsername: List[str]
    destinationAccounts: List[str]
    contentTypes: Dict[str, bool]

class TaskToggle(BaseModel):
    taskId: str
    enabled: bool

class TaskRun(BaseModel):
    taskId: str

# Log Models
class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str
    type: str  # 'info', 'success', 'error'
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Instagram Accounts Management with Real Authentication
@api_router.get("/accounts/list")
async def get_accounts():
    try:
        accounts = await db.instagram_accounts.find().to_list(1000)
        return [{"username": acc["username"], "createdAt": acc["createdAt"]} for acc in accounts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/add")
async def add_account(account_data: InstagramAccountCreate):
    try:
        # Check if account already exists
        existing = await db.instagram_accounts.find_one({"username": account_data.username})
        if existing:
            raise HTTPException(status_code=400, detail="Account already exists")
        
        # Authenticate with Instagram
        success = instagram_engine.add_instagram_account(account_data.username, account_data.password)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to authenticate with Instagram")
        
        # Store account info (without password)
        account_record = {
            "username": account_data.username,
            "createdAt": datetime.utcnow(),
            "authenticated": True
        }
        await db.instagram_accounts.insert_one(account_record)
        
        # Log the action
        log_entry = LogEntry(
            message=f"Added and authenticated Instagram account @{account_data.username}", 
            type="success"
        )
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Account authenticated and added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/accounts/remove")
async def remove_account(account_data: InstagramAccountRemove):
    try:
        result = await db.instagram_accounts.delete_one({"username": account_data.username})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Also remove from active tasks
        await db.tasks.update_many(
            {"destinationAccounts": account_data.username},
            {"$pull": {"destinationAccounts": account_data.username}}
        )
        
        # Log the action
        log_entry = LogEntry(message=f"Removed Instagram account @{account_data.username}", type="info")
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Account removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Tasks Management with Real Instagram Automation
@api_router.get("/tasks/list")
async def get_tasks():
    try:
        # Get tasks from Instagram engine
        engine_tasks = instagram_engine.get_task_status()
        
        # Convert to list format expected by frontend
        tasks = []
        for task_id, task_data in engine_tasks.items():
            tasks.append({
                "id": task_id,
                "name": task_data["name"],
                "sourceUsername": task_data["source_accounts"],
                "destinationAccounts": task_data["destination_accounts"],
                "contentTypes": {ct: True for ct in task_data["content_types"]},
                "enabled": task_data["enabled"],
                "lastRun": task_data.get("last_run"),
                "lastProcessedCount": task_data.get("last_processed_count", 0)
            })
        
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tasks/add")
async def add_task(task_data: TaskCreate):
    try:
        # Validate destination accounts exist
        for username in task_data.destinationAccounts:
            account = await db.instagram_accounts.find_one({"username": username})
            if not account:
                raise HTTPException(status_code=400, detail=f"Destination account @{username} not found")
        
        # Convert content types to list
        content_types = [ct for ct, enabled in task_data.contentTypes.items() if enabled]
        
        # Create task in Instagram engine
        success = instagram_engine.create_monitoring_task(
            task_data.name,
            task_data.sourceUsername,
            task_data.destinationAccounts,
            content_types
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create Instagram monitoring task")
        
        # Log the action
        log_entry = LogEntry(
            message=f"Created Instagram automation task '{task_data.name}' monitoring {len(task_data.sourceUsername)} accounts", 
            type="success"
        )
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Instagram automation task created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tasks/toggle")
async def toggle_task(task_data: TaskToggle):
    try:
        success = instagram_engine.toggle_task(task_data.taskId, task_data.enabled)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")
        
        status = "enabled" if task_data.enabled else "disabled"
        log_entry = LogEntry(message=f"Instagram automation task {status}", type="info")
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": f"Task {status} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tasks/run")
async def run_task(task_data: TaskRun):
    try:
        # Run the Instagram automation task
        result = await instagram_engine.run_task(task_data.taskId)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Task execution failed"))
        
        # Log the action
        processed_count = result.get("processed_count", 0)
        found_count = result.get("found_content", 0)
        
        log_entry = LogEntry(
            message=f"Executed Instagram automation task - found {found_count} items, successfully posted {processed_count} items", 
            type="success"
        )
        await db.logs.insert_one(log_entry.dict())
        
        return {
            "message": f"Task executed successfully - posted {processed_count} items",
            "details": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Logs
@api_router.get("/logs", response_model=List[LogEntry])
async def get_logs():
    logs = await db.logs.find().sort("timestamp", -1).to_list(100)  # Get latest 100 logs
    return [LogEntry(**log) for log in logs]

# Instagram Automation Stats and Monitoring
@api_router.get("/instagram/stats")
async def get_instagram_stats():
    try:
        monitoring_stats = instagram_engine.get_monitoring_stats()
        upload_stats = instagram_engine.get_upload_stats()
        
        return {
            "monitoring": monitoring_stats,
            "uploads": upload_stats,
            "engine_status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/instagram/test-connection")
async def test_instagram_connection():
    try:
        # Test if we have any authenticated accounts
        if not instagram_engine.authenticated_clients:
            return {"status": "no_accounts", "message": "No Instagram accounts authenticated"}
        
        return {
            "status": "connected",
            "accounts": list(instagram_engine.authenticated_clients.keys()),
            "message": "Instagram API connection active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
