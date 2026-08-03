"""
Test that auto-seeding works correctly on application startup in development mode.
This prevents the regression where settings.database_url was incorrectly referenced.
"""
import asyncio
import tempfile
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import after path setup
PROJECT_ROOT = '/opt/data/SigmaFlow'
sys.path.insert(0, PROJECT_ROOT)

from sigmaflow.api.main import app, lifespan, settings
from sigmaflow.core.database import init_db, get_sync_session, close_db_connections
from sigmaflow.core.models import User
from sqlalchemy import select, func


class TestAutoSeed:
    """Test auto-seed functionality on startup."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown test database."""
        # Store original environment
        original_env = os.environ.get('ENVIRONMENT')
        
        # Use a temp directory for test database
        self.temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Override settings to use temp database
        os.environ['DATABASE_URL_SYNC'] = f'sqlite:///{self.temp_dir}/test.db'
        os.environ['DATABASE_URL_ASYNC'] = f'sqlite+aiosqlite:///{self.temp_dir}/test.db'
        os.environ['ENVIRONMENT'] = 'development'
        
        # Add load-tests to path so seed_test_data can be imported
        sys.path.insert(0, os.path.join(PROJECT_ROOT, 'load-tests'))
        
        # Reload settings
        from sigmaflow.core.config import get_settings
        import sigmaflow.api.main as main_module
        main_module.settings = get_settings()
        
        yield
        
        # Cleanup
        os.chdir(original_cwd)
        close_db_connections()
        if original_env:
            os.environ['ENVIRONMENT'] = original_env
        else:
            os.environ.pop('ENVIRONMENT', None)
        os.environ.pop('DATABASE_URL_SYNC', None)
        os.environ.pop('DATABASE_URL_ASYNC', None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_auto_seed_creates_admin_user_on_startup(self):
        """Test that lifespan auto-seeds admin user when database is empty."""
        # Initialize database (creates tables)
        init_db()
        
        # Verify database is empty before lifespan
        with get_sync_session() as session:
            user_count = session.execute(select(func.count(User.id))).scalar()
            assert user_count == 0, "Database should be empty before auto-seed"
        
        # Run lifespan startup (triggers auto-seed)
        async def run_lifespan():
            async with lifespan(app):
                pass
        
        asyncio.run(run_lifespan())
        
        # Verify admin user was created
        with get_sync_session() as session:
            user_count = session.execute(select(func.count(User.id))).scalar()
            assert user_count > 0, "Auto-seed should create users"
            
            admin = session.execute(
                select(User).filter(User.email == 'admin@sigmaflow.com')
            ).scalar_one_or_none()
            assert admin is not None, "Admin user should exist after auto-seed"
            assert admin.is_superuser is True, "Admin should be superuser"
            assert admin.role.value == 'admin', "Admin should have admin role"
    
    def test_auto_seed_only_runs_when_database_empty(self):
        """Test that auto-seed doesn't duplicate users on subsequent startups."""
        # Initialize database
        init_db()
        
        # Run lifespan first time
        async def run_lifespan():
            async with lifespan(app):
                pass
        
        asyncio.run(run_lifespan())
        
        # Get initial user count
        with get_sync_session() as session:
            initial_count = session.execute(select(func.count(User.id))).scalar()
        
        # Run lifespan second time (should not create duplicates)
        asyncio.run(run_lifespan())
        
        # Verify user count is the same
        with get_sync_session() as session:
            final_count = session.execute(select(func.count(User.id))).scalar()
            assert final_count == initial_count, "Auto-seed should not duplicate users"
    
    def test_settings_has_correct_database_url_attributes(self):
        """Test that Settings has database_url_sync and database_url_async, not database_url."""
        # Verify the attributes exist
        assert hasattr(settings, 'database_url_sync'), "Settings should have database_url_sync"
        assert hasattr(settings, 'database_url_async'), "Settings should have database_url_async"
        assert not hasattr(settings, 'database_url'), "Settings should NOT have database_url"
        
        # Verify they are strings
        assert isinstance(settings.database_url_sync, str)
        assert isinstance(settings.database_url_async, str)
        
        # Verify they contain sqlite paths
        assert 'sqlite' in settings.database_url_sync
        assert 'sqlite' in settings.database_url_async


if __name__ == '__main__':
    pytest.main([__file__, '-v'])