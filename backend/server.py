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


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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

# Task Models
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

# Instagram Accounts Management
@api_router.get("/accounts/list", response_model=List[InstagramAccount])
async def get_accounts():
    accounts = await db.instagram_accounts.find().to_list(1000)
    return [InstagramAccount(**account) for account in accounts]

@api_router.post("/accounts/add")
async def add_account(account_data: InstagramAccountCreate):
    try:
        # Check if account already exists
        existing = await db.instagram_accounts.find_one({"username": account_data.username})
        if existing:
            raise HTTPException(status_code=400, detail="Account already exists")
        
        # Create new account (in real implementation, you'd verify credentials with Instagram)
        account = InstagramAccount(username=account_data.username)
        await db.instagram_accounts.insert_one(account.dict())
        
        # Log the action
        log_entry = LogEntry(message=f"Added Instagram account @{account_data.username}", type="success")
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Account added successfully"}
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
        
        # Also remove from any tasks
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

# Tasks Management
@api_router.get("/tasks/list", response_model=List[Task])
async def get_tasks():
    tasks = await db.tasks.find().to_list(1000)
    return [Task(**task) for task in tasks]

@api_router.post("/tasks/add")
async def add_task(task_data: TaskCreate):
    try:
        # Validate destination accounts exist
        for username in task_data.destinationAccounts:
            account = await db.instagram_accounts.find_one({"username": username})
            if not account:
                raise HTTPException(status_code=400, detail=f"Destination account @{username} not found")
        
        task = Task(**task_data.dict())
        await db.tasks.insert_one(task.dict())
        
        # Log the action
        log_entry = LogEntry(
            message=f"Created task '{task_data.name}' monitoring {len(task_data.sourceUsername)} source accounts", 
            type="success"
        )
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Task created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tasks/toggle")
async def toggle_task(task_data: TaskToggle):
    try:
        result = await db.tasks.update_one(
            {"id": task_data.taskId},
            {"$set": {"enabled": task_data.enabled}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        
        status = "enabled" if task_data.enabled else "disabled"
        log_entry = LogEntry(message=f"Task {status}", type="info")
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": f"Task {status} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/tasks/run")
async def run_task(task_data: TaskRun):
    try:
        task = await db.tasks.find_one({"id": task_data.taskId})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Update last run time
        await db.tasks.update_one(
            {"id": task_data.taskId},
            {"$set": {"lastRun": datetime.utcnow(), "lastProcessedCount": 5}}  # Mock processing count
        )
        
        # Log the action
        log_entry = LogEntry(
            message=f"Executed task '{task['name']}' - processed 5 items", 
            type="success"
        )
        await db.logs.insert_one(log_entry.dict())
        
        return {"message": "Task executed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Logs
@api_router.get("/logs", response_model=List[LogEntry])
async def get_logs():
    logs = await db.logs.find().sort("timestamp", -1).to_list(100)  # Get latest 100 logs
    return [LogEntry(**log) for log in logs]

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
