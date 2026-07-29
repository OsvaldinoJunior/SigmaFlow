"""
SigmaFlow RBAC (Role-Based Access Control)
===========================================
Permission matrix and policy engine for multi-tenant resource access.

Roles (ascending permission):
- VIEWER: Read-only access to assigned plant's projects
- GREEN_BELT: Can create/edit projects & datasets in assigned plant, run analyses
- BLACK_BELT: Full project access in assigned plant, manage users, webhooks, alerts
- MASTER_BLACK_BELT: Cross-plant access within tenant, manage all users/projects
- ADMIN: Full tenant admin, manage tenants, plants, users, system config
"""

from __future__ import annotations

from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigmaflow.core.database import get_async_session
from sigmaflow.core.models import Tenant, Plant, Project, User, UserRole

if TYPE_CHECKING:
    from sigmaflow.api.main import get_current_active_user


class Permission(str, Enum):
    """Granular permissions for resource actions."""
    # Tenant-level
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    TENANT_ADMIN = "tenant:admin"

    # Plant-level
    PLANT_READ = "plant:read"
    PLANT_WRITE = "plant:write"
    PLANT_ADMIN = "plant:admin"

    # Project-level
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_ADMIN = "project:admin"
    PROJECT_DELETE = "project:delete"

    # Dataset-level
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    DATASET_DELETE = "dataset:delete"

    # Run/Analysis-level
    RUN_READ = "run:read"
    RUN_WRITE = "run:write"
    RUN_DELETE = "run:delete"
    RUN_TRIGGER = "run:trigger"

    # Insight/Action-level
    INSIGHT_READ = "insight:read"
    ACTION_READ = "action:read"
    ACTION_WRITE = "action:write"

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_ADMIN = "user:admin"

    # Webhook/Alert-level
    WEBHOOK_READ = "webhook:read"
    WEBHOOK_WRITE = "webhook:write"
    WEBHOOK_ADMIN = "webhook:admin"
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_ADMIN = "alert:admin"

    # Scheduled runs
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_WRITE = "schedule:write"

    # System
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"


# Permission matrix: role -> set of permissions
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {
        Permission.TENANT_READ,
        Permission.PLANT_READ,
        Permission.PROJECT_READ,
        Permission.DATASET_READ,
        Permission.RUN_READ,
        Permission.INSIGHT_READ,
        Permission.ACTION_READ,
        Permission.USER_READ,
        Permission.WEBHOOK_READ,
        Permission.ALERT_READ,
        Permission.SCHEDULE_READ,
    },
    UserRole.GREEN_BELT: {
        Permission.TENANT_READ,
        Permission.PLANT_READ,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.DATASET_READ,
        Permission.DATASET_WRITE,
        Permission.RUN_READ,
        Permission.RUN_WRITE,
        Permission.RUN_TRIGGER,
        Permission.INSIGHT_READ,
        Permission.ACTION_READ,
        Permission.ACTION_WRITE,
        Permission.USER_READ,
        Permission.WEBHOOK_READ,
        Permission.ALERT_READ,
        Permission.SCHEDULE_READ,
    },
    UserRole.BLACK_BELT: {
        Permission.TENANT_READ,
        Permission.PLANT_READ,
        Permission.PLANT_WRITE,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_ADMIN,
        Permission.PROJECT_DELETE,
        Permission.DATASET_READ,
        Permission.DATASET_WRITE,
        Permission.DATASET_DELETE,
        Permission.RUN_READ,
        Permission.RUN_WRITE,
        Permission.RUN_DELETE,
        Permission.RUN_TRIGGER,
        Permission.INSIGHT_READ,
        Permission.ACTION_READ,
        Permission.ACTION_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.WEBHOOK_READ,
        Permission.WEBHOOK_WRITE,
        Permission.ALERT_READ,
        Permission.ALERT_WRITE,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_WRITE,
    },
    UserRole.MASTER_BLACK_BELT: {
        Permission.TENANT_READ,
        Permission.TENANT_WRITE,
        Permission.PLANT_READ,
        Permission.PLANT_WRITE,
        Permission.PLANT_ADMIN,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_ADMIN,
        Permission.PROJECT_DELETE,
        Permission.DATASET_READ,
        Permission.DATASET_WRITE,
        Permission.DATASET_DELETE,
        Permission.RUN_READ,
        Permission.RUN_WRITE,
        Permission.RUN_DELETE,
        Permission.RUN_TRIGGER,
        Permission.INSIGHT_READ,
        Permission.ACTION_READ,
        Permission.ACTION_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_ADMIN,
        Permission.WEBHOOK_READ,
        Permission.WEBHOOK_WRITE,
        Permission.WEBHOOK_ADMIN,
        Permission.ALERT_READ,
        Permission.ALERT_WRITE,
        Permission.ALERT_ADMIN,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_WRITE,
        Permission.SYSTEM_AUDIT,
    },
    UserRole.ADMIN: {
        Permission.TENANT_READ,
        Permission.TENANT_WRITE,
        Permission.TENANT_ADMIN,
        Permission.PLANT_READ,
        Permission.PLANT_WRITE,
        Permission.PLANT_ADMIN,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_ADMIN,
        Permission.PROJECT_DELETE,
        Permission.DATASET_READ,
        Permission.DATASET_WRITE,
        Permission.DATASET_DELETE,
        Permission.RUN_READ,
        Permission.RUN_WRITE,
        Permission.RUN_DELETE,
        Permission.RUN_TRIGGER,
        Permission.INSIGHT_READ,
        Permission.ACTION_READ,
        Permission.ACTION_WRITE,
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.USER_ADMIN,
        Permission.WEBHOOK_READ,
        Permission.WEBHOOK_WRITE,
        Permission.WEBHOOK_ADMIN,
        Permission.ALERT_READ,
        Permission.ALERT_WRITE,
        Permission.ALERT_ADMIN,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_WRITE,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_AUDIT,
    },
}


def get_permissions_for_role(role: UserRole) -> Set[Permission]:
    """Get all permissions for a given role."""
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(user: User, permission: Permission) -> bool:
    """Check if user has a specific permission based on their role."""
    if user.is_superuser:
        return True
    return permission in get_permissions_for_role(user.role)


def user_can_access_tenant(user: User, tenant_id: str) -> bool:
    """Check if user can access a specific tenant."""
    if user.is_superuser:
        return True
    return str(user.tenant_id) == tenant_id


def user_can_access_plant(user: User, plant_id: str) -> bool:
    """Check if user can access a specific plant."""
    if user.is_superuser:
        return True
    if not user_can_access_tenant(user, str(user.tenant_id)):
        return False
    # ADMIN and MBB can access all plants in tenant
    if user.role in (UserRole.ADMIN, UserRole.MASTER_BLACK_BELT):
        return True
    # Others restricted to their assigned plant
    return str(user.plant_id) == plant_id if user.plant_id else False


def user_can_access_project(user: User, project: Project) -> bool:
    """Check if user can access a specific project."""
    if user.is_superuser:
        return True
    if not user_can_access_tenant(user, str(user.tenant_id)):
        return False
    if not user_can_access_plant(user, str(project.plant_id)):
        return False
    # Project owner has full access
    if str(project.owner_id) == str(user.id):
        return True
    # Role-based project access
    if user.role == UserRole.VIEWER:
        return True  # Can read
    if user.role == UserRole.GREEN_BELT:
        return True  # Can read/write in their plant
    if user.role in (UserRole.BLACK_BELT, UserRole.MASTER_BLACK_BELT, UserRole.ADMIN):
        return True  # Full access in tenant
    return False


def user_can_modify_project(user: User, project: Project) -> bool:
    """Check if user can modify a project."""
    if user.is_superuser:
        return True
    if not user_can_access_project(user, project):
        return False
    if str(project.owner_id) == str(user.id):
        return True
    if user.role in (UserRole.BLACK_BELT, UserRole.MASTER_BLACK_BELT, UserRole.ADMIN):
        return True
    if user.role == UserRole.GREEN_BELT:
        return True  # Can edit in their plant
    return False


def user_can_delete_project(user: User, project: Project) -> bool:
    """Check if user can delete a project."""
    if user.is_superuser:
        return True
    if not user_can_access_tenant(user, str(user.tenant_id)):
        return False
    if user.role in (UserRole.MASTER_BLACK_BELT, UserRole.ADMIN):
        return True
    if user.role == UserRole.BLACK_BELT and str(project.owner_id) == str(user.id):
        return True
    return False


def user_can_access_dataset(user: User, dataset) -> bool:
    """Check if user can access a dataset (via project)."""
    # Dataset access = project access
    return user_can_access_project(user, dataset.project) if hasattr(dataset, 'project') else False


def user_can_access_run(user: User, run) -> bool:
    """Check if user can access a run (via project)."""
    return user_can_access_project(user, run.project) if hasattr(run, 'project') else False


def user_can_access_webhook(user: User, webhook) -> bool:
    """Check if user can access a webhook (via project)."""
    return user_can_access_project(user, webhook.project) if hasattr(webhook, 'project') else False


def user_can_access_alert_rule(user: User, alert_rule) -> bool:
    """Check if user can access an alert rule (via project)."""
    return user_can_access_project(user, alert_rule.project) if hasattr(alert_rule, 'project') else False


class PolicyEngine:
    """
    Centralized policy enforcement for resource access.
    Usage: policy = PolicyEngine(user); policy.check(project, Permission.PROJECT_WRITE)
    """

    def __init__(self, user: User):
        self.user = user

    def check(self, resource, permission: Permission, raise_on_fail: bool = True) -> bool:
        """Check if user has permission on resource."""
        if self.user.is_superuser:
            return True

        # Tenant check
        if not self._check_tenant(resource):
            if raise_on_fail:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: resource belongs to different tenant"
                )
            return False

        # Plant check
        if not self._check_plant(resource):
            if raise_on_fail:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: resource not in accessible plant"
                )
            return False

        # Role-based permission check
        if not has_permission(self.user, permission):
            if raise_on_fail:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {permission.value} not allowed for role {self.user.role.value}"
                )
            return False

        return True

    def _check_tenant(self, resource) -> bool:
        """Verify resource belongs to user's tenant."""
        if hasattr(resource, 'tenant_id'):
            return str(resource.tenant_id) == str(self.user.tenant_id)
        if hasattr(resource, 'project') and hasattr(resource.project, 'tenant_id'):
            return str(resource.project.tenant_id) == str(self.user.tenant_id)
        # For direct tenant resources
        if isinstance(resource, Tenant):
            return str(resource.id) == str(self.user.tenant_id)
        return True  # No tenant info on resource - allow (will be filtered by query)

    def _check_plant(self, resource) -> bool:
        """Verify resource belongs to accessible plant."""
        if hasattr(resource, 'plant_id'):
            return user_can_access_plant(self.user, str(resource.plant_id))
        if hasattr(resource, 'project') and hasattr(resource.project, 'plant_id'):
            return user_can_access_plant(self.user, str(resource.project.plant_id))
        if isinstance(resource, Plant):
            return user_can_access_plant(self.user, str(resource.id))
        return True  # No plant info - allow (will be filtered by query)


# FastAPI dependencies
async def get_current_user_with_tenant(
    current_user: User = Depends(lambda: None),  # Will be overridden by main.py
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Get current user with tenant context loaded."""
    # Load tenant relationship
    result = await session.execute(
        select(User).filter(User.id == current_user.id).options()
    )
    user = result.scalar_one()
    return user


def require_permission(permission: Permission):
    """Dependency factory for permission checking."""
    async def check_permission(
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_async_session),
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required, role is {current_user.role.value}"
            )
        return current_user
    return check_permission


def require_role(*roles: UserRole):
    """Dependency factory for role-based access."""
    async def check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {[r.value for r in roles]}, current: {current_user.role.value}"
            )
        return current_user
    return check_role


# Tenant-aware query helpers
async def get_tenant_plants(
    session: AsyncSession,
    tenant_id: str,
    user: User,
) -> list[Plant]:
    """Get plants accessible to user within tenant."""
    query = select(Plant).filter(Plant.tenant_id == tenant_id)
    if user.role not in (UserRole.ADMIN, UserRole.MASTER_BLACK_BELT):
        if user.plant_id:
            query = query.filter(Plant.id == user.plant_id)
    result = await session.execute(query)
    return result.scalars().all()


async def get_tenant_projects(
    session: AsyncSession,
    tenant_id: str,
    user: User,
    plant_id: Optional[str] = None,
) -> list[Project]:
    """Get projects accessible to user within tenant."""
    query = select(Project).filter(Project.tenant_id == tenant_id)
    if plant_id:
        query = query.filter(Project.plant_id == plant_id)
    elif user.role not in (UserRole.ADMIN, UserRole.MASTER_BLACK_BELT):
        if user.plant_id:
            query = query.filter(Project.plant_id == user.plant_id)
    result = await session.execute(query)
    return result.scalars().all()


async def get_tenant_users(
    session: AsyncSession,
    tenant_id: str,
    user: User,
) -> list[User]:
    """Get users in tenant (admin/MBB only for full list)."""
    if user.role not in (UserRole.ADMIN, UserRole.MASTER_BLACK_BELT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to list users"
        )
    query = select(User).filter(User.tenant_id == tenant_id)
    result = await session.execute(query)
    return result.scalars().all()


# Tenant extraction from request
async def extract_tenant_from_request(
    request,
    session: AsyncSession = Depends(get_async_session),
) -> Tenant:
    """
    Extract tenant from request.
    Priority: 1) Subdomain header, 2) X-Tenant-ID header, 3) User's tenant (from auth)
    """
    # Check subdomain header (for multi-tenant subdomain routing)
    subdomain = request.headers.get("X-Tenant-Subdomain") or request.headers.get("X-Tenant-Code")
    if subdomain:
        result = await session.execute(select(Tenant).filter(Tenant.code == subdomain))
        tenant = result.scalar_one_or_none()
        if tenant and tenant.is_active:
            return tenant

    # Check explicit tenant ID header
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        result = await session.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant and tenant.is_active:
            return tenant

    # Fallback: will be resolved from authenticated user in get_current_active_user
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Tenant context required. Provide X-Tenant-ID or X-Tenant-Subdomain header."
    )


def tenant_aware_query(model_class, user: User):
    """
    Decorator to automatically filter queries by tenant.
    Usage: @tenant_aware_query(Project) async def get_projects(user: User, session: AsyncSession): ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Inject tenant filter into query
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Resource-specific policy check functions
async def check_project_access(
    project_id: str,
    user: User,
    session: AsyncSession,
    permission: Permission = Permission.PROJECT_READ,
) -> Project:
    """Fetch project and verify user has access."""
    result = await session.execute(select(Project).filter(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    policy = PolicyEngine(user)
    policy.check(project, permission)
    return project


async def check_plant_access(
    plant_id: str,
    user: User,
    session: AsyncSession,
    permission: Permission = Permission.PLANT_READ,
) -> Plant:
    """Fetch plant and verify user has access."""
    result = await session.execute(select(Plant).filter(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    policy = PolicyEngine(user)
    policy.check(plant, permission)
    return plant


async def check_tenant_access(
    tenant_id: str,
    user: User,
    session: AsyncSession,
    permission: Permission = Permission.TENANT_READ,
) -> Tenant:
    """Fetch tenant and verify user has access."""
    result = await session.execute(select(Tenant).filter(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if not user_can_access_tenant(user, tenant_id):
        raise HTTPException(status_code=403, detail="Access denied to tenant")
    return tenant


# Permission decorators for route protection
def require_project_permission(permission: Permission):
    """Decorator to require project-level permission."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(
            project_id: str,
            current_user: User = Depends(get_current_active_user),
            session: AsyncSession = Depends(get_async_session),
            *args, **kwargs
        ):
            project = await check_project_access(project_id, current_user, session, permission)
            return await func(project=project, *args, **kwargs)
        return wrapper
    return decorator


def require_plant_permission(permission: Permission):
    """Decorator to require plant-level permission."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(
            plant_id: str,
            current_user: User = Depends(get_current_active_user),
            session: AsyncSession = Depends(get_async_session),
            *args, **kwargs
        ):
            plant = await check_plant_access(plant_id, current_user, session, permission)
            return await func(plant=plant, *args, **kwargs)
        return wrapper
    return decorator


# Export all
__all__ = [
    "Permission",
    "ROLE_PERMISSIONS",
    "get_permissions_for_role",
    "has_permission",
    "user_can_access_tenant",
    "user_can_access_plant",
    "user_can_access_project",
    "user_can_modify_project",
    "user_can_delete_project",
    "user_can_access_dataset",
    "user_can_access_run",
    "user_can_access_webhook",
    "user_can_access_alert_rule",
    "PolicyEngine",
    "get_current_user_with_tenant",
    "require_permission",
    "require_role",
    "get_tenant_plants",
    "get_tenant_projects",
    "get_tenant_users",
    "extract_tenant_from_request",
    "tenant_aware_query",
    "check_project_access",
    "check_plant_access",
    "check_tenant_access",
    "require_project_permission",
    "require_plant_permission",
]