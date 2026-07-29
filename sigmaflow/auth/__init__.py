"""
SigmaFlow Authentication & Authorization
=========================================
JWT authentication + RBAC multi-tenant authorization.
"""

from __future__ import annotations

from sigmaflow.auth.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    get_permissions_for_role,
    has_permission,
    user_can_access_tenant,
    user_can_access_plant,
    user_can_access_project,
    user_can_modify_project,
    user_can_delete_project,
    user_can_access_dataset,
    user_can_access_run,
    user_can_access_webhook,
    user_can_access_alert_rule,
    PolicyEngine,
    require_permission,
    require_role,
    get_tenant_plants,
    get_tenant_projects,
    get_tenant_users,
    extract_tenant_from_request,
    check_project_access,
    check_plant_access,
    check_tenant_access,
    require_project_permission,
    require_plant_permission,
)

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
    "require_permission",
    "require_role",
    "get_tenant_plants",
    "get_tenant_projects",
    "get_tenant_users",
    "extract_tenant_from_request",
    "check_project_access",
    "check_plant_access",
    "check_tenant_access",
    "require_project_permission",
    "require_plant_permission",
]