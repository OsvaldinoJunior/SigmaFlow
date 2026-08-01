-- SigmaFlow Database Initialization Script
-- ========================================
-- Run this on first database creation to set up extensions and initial data

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Create custom types if needed
-- (These are typically created by Alembic migrations, but included here for reference)

-- Set timezone
SET timezone = 'America/Sao_Paulo';

-- Create indexes for better performance (run after migrations)
-- These are examples - actual indexes should be created via Alembic migrations

-- Example indexes for common queries:
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_tenant_email ON users(tenant_id, email);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_tenant_status ON projects(tenant_id, status);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_runs_tenant_project_status ON runs(tenant_id, project_id, status);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_insights_tenant_run ON insights(tenant_id, run_id);
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_action_items_tenant_project_status ON action_items(tenant_id, project_id, status);

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sigmaflow;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sigmaflow;
-- GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO sigmaflow;

-- Set default privileges for future objects
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sigmaflow;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sigmaflow;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sigmaflow;

-- Verify setup
SELECT 'Database initialization complete' AS status;