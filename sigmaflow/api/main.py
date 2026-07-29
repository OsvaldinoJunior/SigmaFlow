"""
SigmaFlow FastAPI Application
==============================
REST API for the SigmaFlow enterprise platform.
Multi-tenant with RBAC authorization.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sigmaflow.core.config import get_settings
from sigmaflow.core.database import get_async_session, init_db, close_db_connections
from sigmaflow.core.models import (
    Tenant, Plant, User, Project, Dataset, Run, PhaseResult, Insight,
    ActionItem, ScheduledRun, UserRole, RunStatus, PhaseName,
    InsightSeverity, ActionStatus
)
from sigmaflow.worker.tasks import run_pipeline, run_scheduled_pipelines
from sigmaflow.worker.celery_app import celery_app
from sigmaflow.alerts.routes import router as alerts_router
from sigmaflow.auth import (
    get_current_user_with_tenant,
    check_project_access,
    check_plant_access,
    check_tenant_access,
    require_project_permission,
    require_plant_permission,
    Permission,
)

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
    tenant_id: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.VIEWER
    plant_id: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    plant_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    tenant_id: str
    plant_id: Optional[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TenantCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None


class TenantResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str]
    domain: Optional[str]
    is_active: bool
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
    tenant_id: str
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
    tenant_id: str
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
    tenant_id: str
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
    tenant_id: str
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
    tenant_id: str
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
    tenant_id: str
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
    tenant_id: str
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


# Extended version with tenant context
async def get_current_user_with_tenant(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Ensure user has tenant loaded and valid."""
    result = await session.execute(select(Tenant).filter(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Tenant not active")
    current_user.tenant = tenant
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
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Register a new user within the current tenant."""
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.TENANT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create users")

    result = await session.execute(select(User).filter(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_data.plant_id:
        result = await session.execute(
            select(Plant).filter(Plant.id == user_data.plant_id, Plant.tenant_id == current_user.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Plant not found in tenant")

    user = User(
        tenant_id=current_user.tenant_id,
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
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "type": "refresh"},
        expires_delta=timedelta(days=7),
    )

    user.last_login = datetime.now(timezone.utc)
    await session.commit()

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user_with_tenant)):
    """Get current user info with tenant context."""
    return current_user


@app.patch("/api/v1/auth/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update current user profile."""
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    current_user.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(current_user)
    return current_user


# ── Tenant Endpoints ──────────────────────────────────────────────────────────

@app.post("/api/v1/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant: TenantCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new tenant (superuser only in production)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can create tenants")

    result = await session.execute(select(Tenant).filter(Tenant.code == tenant.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Tenant code already exists")

    if tenant.domain:
        result = await session.execute(select(Tenant).filter(Tenant.domain == tenant.domain))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Tenant domain already exists")

    new_tenant = Tenant(**tenant.model_dump())
    session.add(new_tenant)
    await session.commit()
    await session.refresh(new_tenant)
    return new_tenant


@app.get("/api/v1/tenants", response_model=list[TenantResponse])
async def list_tenants(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List tenants (superuser sees all, others see own)."""
    if current_user.is_superuser:
        result = await session.execute(select(Tenant).filter(Tenant.is_active == True))
    else:
        result = await session.execute(select(Tenant).filter(Tenant.id == current_user.tenant_id))
    return result.scalars().all()


@app.get("/api/v1/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific tenant."""
    if not current_user.is_superuser and str(current_user.tenant_id) != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = await session.execute(select(Tenant).filter(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


# ── Plant Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/v1/plants", response_model=PlantResponse, status_code=status.HTTP_201_CREATED)
async def create_plant(
    plant: PlantCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new plant in current tenant."""
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.TENANT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await session.execute(
        select(Plant).filter(Plant.tenant_id == current_user.tenant_id, Plant.code == plant.code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Plant code already exists in tenant")

    new_plant = Plant(tenant_id=current_user.tenant_id, **plant.model_dump())
    session.add(new_plant)
    await session.commit()
    await session.refresh(new_plant)
    return new_plant


@app.get("/api/v1/plants", response_model=list[PlantResponse])
async def list_plants(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List plants in current tenant (filtered by user role/plant)."""
    from sigmaflow.auth import get_tenant_plants
    return await get_tenant_plants(session, current_user)


@app.get("/api/v1/plants/{plant_id}", response_model=PlantResponse)
async def get_plant(
    plant_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific plant."""
    plant = await check_plant_access(plant_id, current_user, session)
    return plant


@app.patch("/api/v1/plants/{plant_id}", response_model=PlantResponse)
async def update_plant(
    plant_id: str,
    code: Optional[str] = None,
    name: Optional[str] = None,
    country: Optional[str] = None,
    timezone: Optional[str] = None,
    is_active: Optional[bool] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update a plant."""
    plant = await check_plant_access(plant_id, current_user, session, Permission.PLANT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PLANT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for field, value in [("code", code), ("name", name), ("country", country),
                          ("timezone", timezone), ("is_active", is_active)]:
        if value is not None:
            setattr(plant, field, value)
    plant.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(plant)
    return plant


# ── Project Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v1/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new project in current tenant."""
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create projects")

    result = await session.execute(
        select(Plant).filter(Plant.id == project.plant_id, Plant.tenant_id == current_user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Plant not found in tenant")

    result = await session.execute(
        select(User).filter(User.id == project.owner_id, User.tenant_id == current_user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Owner not found in tenant")

    result = await session.execute(
        select(Project).filter(Project.tenant_id == current_user.tenant_id, Project.code == project.code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Project code already exists in tenant")

    new_project = Project(tenant_id=current_user.tenant_id, **project.model_dump())
    session.add(new_project)
    await session.commit()
    await session.refresh(new_project)
    return new_project


@app.get("/api/v1/projects", response_model=list[ProjectResponse])
async def list_projects(
    plant_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List projects in current tenant (filtered by user access)."""
    from sigmaflow.auth import get_tenant_projects
    return await get_tenant_projects(session, current_user, plant_id, status)


@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific project with tenant isolation."""
    project = await check_project_access(project_id, current_user, session)
    return project


@app.patch("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    problem_statement: Optional[str] = None,
    goal_statement: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update a project."""
    project = await check_project_access(project_id, current_user, session, Permission.PROJECT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for field, value in [
        ("name", name), ("description", description),
        ("problem_statement", problem_statement), ("goal_statement", goal_statement),
        ("status", status)
    ]:
        if value is not None:
            setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(project)
    return project


@app.delete("/api/v1/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Delete a project (owner/MBB/Admin only)."""
    project = await check_project_access(project_id, current_user, session, Permission.PROJECT_DELETE)
    from sigmaflow.auth import user_can_delete_project, has_permission, Permission
    if not user_can_delete_project(current_user, project):
        raise HTTPException(status_code=403, detail="Only owner, MBB, or Admin can delete project")

    await session.delete(project)
    await session.commit()


# ── Dataset Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/v1/projects/{project_id}/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    project_id: str,
    dataset: DatasetCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a dataset in a project."""
    project = await check_project_access(project_id, current_user, session, Permission.PROJECT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    new_dataset = Dataset(
        tenant_id=current_user.tenant_id,
        project_id=project.id,
        created_by_id=current_user.id,
        **dataset.model_dump()
    )
    session.add(new_dataset)
    await session.commit()
    await session.refresh(new_dataset)
    return new_dataset


@app.get("/api/v1/projects/{project_id}/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    project_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List datasets in a project."""
    await check_project_access(project_id, current_user, session, Permission.PROJECT_READ)
    result = await session.execute(
        select(Dataset).filter(
            Dataset.tenant_id == current_user.tenant_id,
            Dataset.project_id == project_id,
            Dataset.is_active == True
        ).order_by(Dataset.created_at.desc())
    )
    return result.scalars().all()


# ── Run Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/v1/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run: RunCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new pipeline run."""
    result = await session.execute(
        select(Project).filter(Project.code == run.project_code, Project.tenant_id == current_user.tenant_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await check_project_access(str(project.id), current_user, session, Permission.PROJECT_READ)

    if run.dataset_name:
        result = await session.execute(
            select(Dataset).filter(
                Dataset.project_id == project.id,
                Dataset.name == run.dataset_name,
                Dataset.is_active == True,
                Dataset.tenant_id == current_user.tenant_id
            )
        )
    else:
        result = await session.execute(
            select(Dataset).filter(
                Dataset.project_id == project.id,
                Dataset.is_active == True,
                Dataset.tenant_id == current_user.tenant_id
            ).order_by(Dataset.created_at.desc())
        )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="No active dataset found")

    task = run_pipeline.delay(
        project_code=run.project_code,
        dataset_name=dataset.name,
        run_config=run.config,
        triggered_by="api",
        tenant_id=str(current_user.tenant_id),
    )

    new_run = Run(
        tenant_id=current_user.tenant_id,
        project_id=project.id,
        dataset_id=dataset.id,
        run_number=1,
        status=RunStatus.PENDING,
        config_json=run.config,
        triggered_by="api",
        created_by_id=current_user.id,
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
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List runs for a project."""
    await check_project_access(project_id, current_user, session, Permission.PROJECT_READ)
    query = select(Run).filter(Run.tenant_id == current_user.tenant_id, Run.project_id == project_id)
    if status:
        query = query.filter(Run.status == status)
    query = query.order_by(Run.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get a specific run."""
    result = await session.execute(
        select(Run).filter(Run.id == run_id, Run.tenant_id == current_user.tenant_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await check_project_access(str(run.project_id), current_user, session, Permission.PROJECT_READ)
    return run


@app.get("/api/v1/runs/{run_id}/insights", response_model=list[InsightResponse])
async def get_run_insights(
    run_id: str,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Get insights for a run."""
    result = await session.execute(
        select(Run).filter(Run.id == run_id, Run.tenant_id == current_user.tenant_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await check_project_access(str(run.project_id), current_user, session, Permission.PROJECT_READ)

    result = await session.execute(
        select(Insight).filter(
            Insight.tenant_id == current_user.tenant_id,
            Insight.run_id == run_id
        ).order_by(Insight.created_at.desc())
    )
    return result.scalars().all()


# ── Action Items Endpoints ────────────────────────────────────────────────────

@app.post("/api/v1/action-items", response_model=ActionItemResponse, status_code=status.HTTP_201_CREATED)
async def create_action_item(
    item: ActionItemCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a new action item."""
    await check_project_access(item.project_id, current_user, session, Permission.PROJECT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    new_item = ActionItem(
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        **item.model_dump()
    )
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
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List action items for a project."""
    await check_project_access(project_id, current_user, session, Permission.PROJECT_READ)
    query = select(ActionItem).filter(
        ActionItem.tenant_id == current_user.tenant_id,
        ActionItem.project_id == project_id
    )
    if status:
        query = query.filter(ActionItem.status == status)
    if assignee_id:
        query = query.filter(ActionItem.assignee_id == assignee_id)
    result = await session.execute(query.order_by(ActionItem.priority, ActionItem.due_date))
    return result.scalars().all()


@app.patch("/api/v1/action-items/{item_id}", response_model=ActionItemResponse)
async def update_action_item(
    item_id: str,
    status: Optional[ActionStatus] = None,
    assignee_id: Optional[str] = None,
    due_date: Optional[datetime] = None,
    evidence_urls: Optional[list[str]] = None,
    verification_notes: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update an action item."""
    result = await session.execute(
        select(ActionItem).filter(
            ActionItem.id == item_id,
            ActionItem.tenant_id == current_user.tenant_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    await check_project_access(str(item.project_id), current_user, session, Permission.PROJECT_WRITE)

    if status:
        item.status = status
        if status == ActionStatus.IN_PROGRESS and not item.started_at:
            item.started_at = datetime.now(timezone.utc)
        if status == ActionStatus.DONE and not item.completed_at:
            item.completed_at = datetime.now(timezone.utc)
        if status == ActionStatus.VERIFIED and not item.verified_at:
            item.verified_at = datetime.now(timezone.utc)
            item.verified_by_id = current_user.id

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

@app.post("/api/v1/scheduled-runs", response_model=ScheduledRunResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_run(
    schedule: ScheduledRunCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Create a scheduled run."""
    await check_project_access(schedule.project_id, current_user, session, Permission.PROJECT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    new_schedule = ScheduledRun(tenant_id=current_user.tenant_id, **schedule.model_dump())
    session.add(new_schedule)
    await session.commit()
    await session.refresh(new_schedule)
    return new_schedule


@app.get("/api/v1/scheduled-runs", response_model=list[ScheduledRunResponse])
async def list_scheduled_runs(
    project_id: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """List scheduled runs."""
    query = select(ScheduledRun).filter(ScheduledRun.tenant_id == current_user.tenant_id)
    if project_id:
        await check_project_access(project_id, current_user, session, Permission.PROJECT_READ)
        query = query.filter(ScheduledRun.project_id == project_id)
    result = await session.execute(query.order_by(ScheduledRun.created_at.desc()))
    return result.scalars().all()


@app.patch("/api/v1/scheduled-runs/{schedule_id}", response_model=ScheduledRunResponse)
async def update_scheduled_run(
    schedule_id: str,
    enabled: Optional[bool] = None,
    cron_expression: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_with_tenant),
):
    """Update a scheduled run."""
    result = await session.execute(
        select(ScheduledRun).filter(
            ScheduledRun.id == schedule_id,
            ScheduledRun.tenant_id == current_user.tenant_id
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await check_project_access(str(schedule.project_id), current_user, session, Permission.PROJECT_WRITE)
    from sigmaflow.auth import has_permission, Permission
    if not has_permission(current_user.role, Permission.PROJECT_WRITE):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if enabled is not None:
        schedule.enabled = enabled
    if cron_expression:
        schedule.cron_expression = cron_expression

    schedule.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(schedule)
    return schedule


# ── Router Registration ────────────────────────────────────────────────────────

app.include_router(alerts_router, prefix="/api/v1", tags=["alerts"])


# ── Health & Info ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    from sigmaflow.core.database import check_db_connection_async
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
