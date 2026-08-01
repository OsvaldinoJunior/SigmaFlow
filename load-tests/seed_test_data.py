"""
Seed Test Data for SigmaFlow Load Tests
========================================
Creates test tenants, plants, and users for load testing.

Run with: python load-tests/seed_test_data.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext

from sigmaflow.core.config import get_settings
from sigmaflow.core.models import (
    Tenant, Plant, User, UserRole
)

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test data configuration
TENANTS_DATA = [
    {
        "code": "tenant-acme",
        "name": "ACME Corp",
        "description": "Load test tenant - ACME Corporation",
        "domain": "acme.loadtest.local",
    },
    {
        "code": "tenant-globex",
        "name": "Globex Inc",
        "description": "Load test tenant - Globex Incorporated",
        "domain": "globex.loadtest.local",
    },
    {
        "code": "tenant-initech",
        "name": "Initech LLC",
        "description": "Load test tenant - Initech LLC",
        "domain": "initech.loadtest.local",
    },
    {
        "code": "tenant-umbrella",
        "name": "Umbrella Corp",
        "description": "Load test tenant - Umbrella Corporation",
        "domain": "umbrella.loadtest.local",
    },
    {
        "code": "tenant-wayne",
        "name": "Wayne Enterprises",
        "description": "Load test tenant - Wayne Enterprises",
        "domain": "wayne.loadtest.local",
    },
]

PLANT_DATA = {
    "tenant-acme": [
        {"code": "plant-acme-1", "name": "ACME Plant 1", "country": "US", "timezone": "America/New_York"},
        {"code": "plant-acme-2", "name": "ACME Plant 2", "country": "US", "timezone": "America/Chicago"},
    ],
    "tenant-globex": [
        {"code": "plant-globex-1", "name": "Globex HQ Plant", "country": "US", "timezone": "America/Los_Angeles"},
    ],
    "tenant-initech": [
        {"code": "plant-initech-1", "name": "Initech Main", "country": "US", "timezone": "America/Denver"},
    ],
    "tenant-umbrella": [
        {"code": "plant-umbrella-1", "name": "Umbrella R&D", "country": "US", "timezone": "America/New_York"},
        {"code": "plant-umbrella-2", "name": "Umbrella Manufacturing", "country": "US", "timezone": "America/Chicago"},
    ],
    "tenant-wayne": [
        {"code": "plant-wayne-1", "name": "Wayne Industries", "country": "US", "timezone": "America/New_York"},
    ],
}

USERS_PER_TENANT = 5
USER_PASSWORD = "TestPass123!"
ADMIN_EMAIL = "admin@sigmaflow.com"
ADMIN_PASSWORD = "AdminPass123!"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def seed_database():
    """Seed the database with test data."""
    
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("=" * 60)
        print("Seeding SigmaFlow Test Data")
        print("=" * 60)
        
        # Create tenants
        tenant_map = {}
        for tenant_data in TENANTS_DATA:
            # Check if tenant exists
            result = await session.execute(
                select(Tenant).filter(Tenant.code == tenant_data["code"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"Tenant {tenant_data['code']} already exists, skipping...")
                tenant_map[tenant_data["code"]] = existing
            else:
                tenant = Tenant(**tenant_data, is_active=True)
                session.add(tenant)
                await session.flush()
                tenant_map[tenant_data["code"]] = tenant
                print(f"Created tenant: {tenant_data['code']} ({tenant_data['name']})")
        
        await session.commit()
        
        # Create plants
        plant_map = {}
        for tenant_code, plants in PLANT_DATA.items():
            tenant = tenant_map[tenant_code]
            plant_map[tenant_code] = []
            
            for plant_data in plants:
                result = await session.execute(
                    select(Plant).filter(
                        Plant.tenant_id == tenant.id,
                        Plant.code == plant_data["code"]
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"  Plant {plant_data['code']} already exists, skipping...")
                    plant_map[tenant_code].append(existing)
                else:
                    plant = Plant(tenant_id=tenant.id, **plant_data, is_active=True)
                    session.add(plant)
                    await session.flush()
                    plant_map[tenant_code].append(plant)
                    print(f"  Created plant: {plant_data['code']} ({plant_data['name']})")
        
        await session.commit()
        
        # Create regular users
        for tenant_code, tenant in tenant_map.items():
            plants = plant_map.get(tenant_code, [])
            default_plant = plants[0] if plants else None
            
            for i in range(1, USERS_PER_TENANT + 1):
                email = f"user{i}@{tenant_code}.com"
                
                result = await session.execute(
                    select(User).filter(User.email == email)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"  User {email} already exists, skipping...")
                else:
                    # Assign roles: user1=ADMIN, user2=MBB, user3=BLACK_BELT, user4=GREEN_BELT, user5=VIEWER
                    roles = [UserRole.ADMIN, UserRole.MBB, UserRole.BLACK_BELT, UserRole.GREEN_BELT, UserRole.VIEWER]
                    role = roles[i - 1]
                    
                    user = User(
                        tenant_id=tenant.id,
                        email=email,
                        full_name=f"Test User {i} ({tenant_code})",
                        hashed_password=get_password_hash(USER_PASSWORD),
                        role=role,
                        plant_id=default_plant.id if default_plant else None,
                        is_active=True,
                        is_superuser=(role == UserRole.ADMIN),
                    )
                    session.add(user)
                    print(f"  Created user: {email} (role: {role.value})")
        
        # Create super admin user
        result = await session.execute(
            select(User).filter(User.email == ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Admin user {ADMIN_EMAIL} already exists, skipping...")
        else:
            # Get first tenant for admin
            first_tenant = list(tenant_map.values())[0]
            admin = User(
                tenant_id=first_tenant.id,
                email=ADMIN_EMAIL,
                full_name="SigmaFlow Administrator",
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
                is_superuser=True,
            )
            session.add(admin)
            print(f"Created admin user: {ADMIN_EMAIL}")
        
        await session.commit()
        
        print("=" * 60)
        print("Seeding Complete!")
        print("=" * 60)
        print("\nTest Credentials:")
        print("-" * 40)
        for tenant_code in tenant_map.keys():
            for i in range(1, USERS_PER_TENANT + 1):
                print(f"  user{i}@{tenant_code}.com / {USER_PASSWORD}")
        print(f"  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("-" * 40)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())