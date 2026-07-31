"""
SigmaFlow FastAPI Application
==============================
REST API for the SigmaFlow enterprise platform.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sigmaflow.core.config import get_settings
from sigmaflow.core.database import get_async_session, init_db, close_db_connections
from sigmaflow.core.models import (
    Plant, User, Project, Dataset, Run, PhaseResult, Insight,
    ActionItem, ScheduledRun, UserRole, RunStatus, PhaseName,
    InsightSeverity, ActionStatus
)
from sigmaflow.worker.tasks import run_pipeline, run_scheduled_pipelines
from sigmaflow.worker.celery_app import celery_app

settings = get_settings()

# Password hashing
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT
from jose import jwt, JWTError

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Pydantic Models ───────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.VIEWER
    plant_id: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    plant_id: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PlantCreate(BaseModel):
    code: str
    name: str
    country: str = "BR"
    timezone: str = "America/Sao_Paulo"


class PlantResponse(BaseModel):
    id: str
    code: str
    name: str
    country: str
    timezone: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    code: str
    name: str
    plant_id: str
    owner_id: str
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    goal_statement: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    code: str
    name: str
    plant_id: str
    owner_id: str
    description: Optional[str]
    problem_statement: Optional[str]
    goal_statement: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: str
    source_config: dict = {}
    file_path: Optional[str] = None


class DatasetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str]
    version: int
    source_type: str
    row_count: Optional[int]
    column_count: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RunCreate(BaseModel):
    project_code: str
    dataset_name: Optional[str] = None
    config: dict = {}


class RunResponse(BaseModel):
    id: str
    project_id: str
    dataset_id: Optional[str]
    run_number: int
    status: RunStatus
    triggered_by: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    elapsed_seconds: Optional[float]
    insights_count: int
    critical_insights_count: int
    warning_insights_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class InsightResponse(BaseModel):
    id: str
    run_id: str
    phase: Optional[PhaseName]
    rule_id: str
    description: str
    meaning: Optional[str]
    recommendation: Optional[str]
    severity: InsightSeverity
    created_at: datetime

    class Config:
        from_attributes = True


class ActionItemCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: int = 1
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None


class ActionItemResponse(BaseModel):
    id: str
    project_id: str
    insight_id: Optional[str]
    title: str
    description: Optional[str]
    category: Optional[str]
    priority: int
    status: ActionStatus
    assignee_id: Optional[str]
    due_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduledRunCreate(BaseModel):
    project_id: str
    cron_expression: str
    timezone: str = "America/Sao_Paulo"
    dataset_name: Optional[str] = None
    run_config: dict = {}


class ScheduledRunResponse(BaseModel):
    id: str
    project_id: str
    cron_expression: str
    timezone: str
    dataset_name: Optional[str]
    enabled: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Auth Helpers ──────────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    close_db_connections()


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SigmaFlow API",
    description="Enterprise Lean Six Sigma DMAIC Automation Platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_async_session)):
    """Register a new user."""
    # Check if user exists
    result = await session.execute(select(User).filter(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Verify plant if provided
    if user_data.plant_id:
        result = await session.execute(select(Plant).filter(Plant.id == user_data.plant_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Plant not found")

    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        plant_id=user_data.plant_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@app.post("/api/v1/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """Login and get access token."""
    result = await session.execute(select(User).filter(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_access_token(
        data={"sub": str(user.id), "type": "refresh"},
        expires_delta=timedelta(days=7),
    )

    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current user info."""
    return current_user


# ── Plant Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/v1/plants", response_model=PlantResponse)
async def create_plant(plant: PlantCreate, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Plant).filter(Plant.code == plant.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Plant code already exists")

    new_plant = Plant(**plant.model_dump())
    session.add(new_plant)
    await session.commit()
    await session.refresh(new_plant)
    return new_plant


@app.get("/api/v1/plants", response_model=list[PlantResponse])
async def list_plants(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Plant).filter(Plant.is_active == True))
    return result.scalars().all()


@app.get("/api/v1/plants/{plant_id}", response_model=PlantResponse)
async def get_plant(plant_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Plant).filter(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


# ── Project Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v1/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, session: AsyncSession = Depends(get_async_session)):
    # Validate plant
    result = await session.execute(select(Plant).filter(Plant.id == project.plant_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Plant not found")

    # Validate owner
    result = await session.execute(select(User).filter(User.id == project.owner_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Owner not found")

    # Check code unique
    result = await session.execute(select(Project).filter(Project.code == project.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Project code already exists")

    new_project = Project(**project.model_dump())
    session.add(new_project)
    await session.commit()
    await session.refresh(new_project)
    return new_project


@app.get("/api/v1/projects", response_model=list[ProjectResponse])
async def list_projects(
    plant_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(Project)
    if plant_id:
        query = query.filter(Project.plant_id == plant_id)
    if status:
        query = query.filter(Project.status == status)
    result = await session.execute(query.order_by(Project.created_at.desc()))
    return result.scalars().all()


@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Project).filter(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Dataset Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/datasets", response_model=DatasetResponse)
async def create_dataset(
    project_id: str,
    dataset: DatasetCreate,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(Project).filter(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    new_dataset = Dataset(project_id=project_id, **dataset.model_dump())
    session.add(new_dataset)
    await session.commit()
    await session.refresh(new_dataset)
    return new_dataset


@app.get("/api/v1/projects/{project_id}/datasets", response_model=list[DatasetResponse])
async def list_datasets(project_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(
        select(Dataset).filter(
            Dataset.project_id == project_id,
            Dataset.is_active == True
        ).order_by(Dataset.created_at.desc())
    )
    return result.scalars().all()


# ── Run Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/v1/runs", response_model=RunResponse)
async def create_run(
    run: RunCreate,
    background_tasks: Any,
    session: AsyncSession = Depends(get_async_session),
):
    # Validate project
    result = await session.execute(select(Project).filter(Project.code == run.project_code))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get dataset
    if run.dataset_name:
        result = await session.execute(
            select(Dataset).filter(
                Dataset.project_id == project.id,
                Dataset.name == run.dataset_name,
                Dataset.is_active == True
            )
        )
    else:
        result = await session.execute(
            select(Dataset).filter(
                Dataset.project_id == project.id,
                Dataset.is_active == True
            ).order_by(Dataset.created_at.desc())
        )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="No active dataset found")

    # Queue pipeline task
    task = run_pipeline.delay(
        project_code=run.project_code,
        dataset_name=dataset.name,
        run_config=run.config,
        triggered_by="api",
    )

    # Create run record
    new_run = Run(
        project_id=project.id,
        dataset_id=dataset.id,
        run_number=1,  # Will be updated by task
        status=RunStatus.PENDING,
        config_json=run.config,
        triggered_by="api",
    )
    session.add(new_run)
    await session.commit()
    await session.refresh(new_run)

    return new_run


@app.get("/api/v1/projects/{project_id}/runs", response_model=list[RunResponse])
async def list_runs(
    project_id: str,
    status: Optional[RunStatus] = None,
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_async_session),
):
    query = select(Run).filter(Run.project_id == project_id)
    if status:
        query = query.filter(Run.status == status)
    query = query.order_by(Run.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Run).filter(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/v1/runs/{run_id}/insights", response_model=list[InsightResponse])
async def get_run_insights(run_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(
        select(Insight).filter(Insight.run_id == run_id).order_by(Insight.created_at.desc())
    )
    return result.scalars().all()


# ── Action Items Endpoints ────────────────────────────────────────────────────

@app.post("/api/v1/action-items", response_model=ActionItemResponse)
async def create_action_item(item: ActionItemCreate, session: AsyncSession = Depends(get_async_session)):
    new_item = ActionItem(**item.model_dump())
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item


@app.get("/api/v1/projects/{project_id}/action-items", response_model=list[ActionItemResponse])
async def list_action_items(
    project_id: str,
    status: Optional[ActionStatus] = None,
    assignee_id: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(ActionItem).filter(ActionItem.project_id == project_id)
    if status:
        query = query.filter(ActionItem.status == status)
    if assignee_id:
        query = query.filter(ActionItem.assignee_id == assignee_id)
    result = await session.execute(query.order_by(ActionItem.priority, ActionItem.due_date))
    return result.scalars().all()


@app.patch("/api/v1/action-items/{item_id}")
async def update_action_item(
    item_id: str,
    status: Optional[ActionStatus] = None,
    assignee_id: Optional[str] = None,
    due_date: Optional[datetime] = None,
    evidence_urls: Optional[list[str]] = None,
    verification_notes: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(ActionItem).filter(ActionItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    if status:
        item.status = status
        if status == ActionStatus.IN_PROGRESS and not item.started_at:
            item.started_at = datetime.now(timezone.utc)
        if status == ActionStatus.DONE and not item.completed_at:
            item.completed_at = datetime.now(timezone.utc)
        if status == ActionStatus.VERIFIED and not item.verified_at:
            item.verified_at = datetime.now(timezone.utc)

    if assignee_id:
        item.assignee_id = assignee_id
    if due_date:
        item.due_date = due_date
    if evidence_urls:
        item.evidence_urls = evidence_urls
    if verification_notes:
        item.verification_notes = verification_notes

    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)
    return item


# ── Scheduled Runs Endpoints ──────────────────────────────────────────────────

@app.post("/api/v1/scheduled-runs", response_model=ScheduledRunResponse)
async def create_scheduled_run(schedule: ScheduledRunCreate, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Project).filter(Project.id == schedule.project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    new_schedule = ScheduledRun(**schedule.model_dump())
    session.add(new_schedule)
    await session.commit()
    await session.refresh(new_schedule)
    return new_schedule


@app.get("/api/v1/scheduled-runs", response_model=list[ScheduledRunResponse])
async def list_scheduled_runs(
    project_id: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    query = select(ScheduledRun)
    if project_id:
        query = query.filter(ScheduledRun.project_id == project_id)
    result = await session.execute(query.order_by(ScheduledRun.created_at.desc()))
    return result.scalars().all()


@app.patch("/api/v1/scheduled-runs/{schedule_id}")
async def update_scheduled_run(
    schedule_id: str,
    enabled: Optional[bool] = None,
    cron_expression: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(ScheduledRun).filter(ScheduledRun.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if enabled is not None:
        schedule.enabled = enabled
    if cron_expression:
        schedule.cron_expression = cron_expression

    schedule.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(schedule)
    return schedule


# ── Health & Info ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    db_ok = await check_db_connection_async()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": "0.2.0",
    }


@app.get("/api/v1/info")
async def info():
    return {
        "name": "SigmaFlow",
        "version": "0.2.0",
        "description": "Enterprise Lean Six Sigma DMAIC Automation Platform",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def check_db_connection_async() -> bool:
    try:
        async with get_async_session() as session:
            await session.execute(select(1))
        return True
    except Exception:
        return False